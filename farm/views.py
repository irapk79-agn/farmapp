from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import Block, Row, DURATION_CHOICES


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'farm/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def _owner_for_user(user):
    """Match a logged-in user to an Owner by username (case-insensitive)."""
    from .models import Owner
    return Owner.objects.filter(name__iexact=user.username).first()

@login_required
def dashboard(request):
    if request.user.is_superuser or request.user.is_staff:
        qs = Block.objects.prefetch_related('rows')
        visible_blocks = {b.block_number: b for b in qs}
    else:
        owner = _owner_for_user(request.user)
        if owner is None:
            visible_blocks = {}
        else:
            qs = Block.objects.filter(owner=owner).prefetch_related('rows')
            visible_blocks = {b.block_number: b for b in qs}

    # Build a list of (number, block_or_None) for all 100 slots
    grid = []
    for n in range(1, 101):
        grid.append((n, visible_blocks.get(n)))

    # Summary counts — only on visible blocks
    visible_qs = Block.objects.filter(block_number__in=[n for n, b in grid if b])
    rows_qs = Row.objects.filter(block__in=visible_qs)
    status_counts = {
        'PLOWING': rows_qs.filter(status='PLOWING').count(),
        'SEEDING': rows_qs.filter(status='SEEDING').count(),
        'WATERING': rows_qs.filter(status='WATERING').count(),
        'READY_TO_HARVEST': rows_qs.filter(status='READY_TO_HARVEST').count(),
        'HARVESTED': rows_qs.filter(status='HARVESTED').count(),
    }

    # Land-wide allocation counts (all 100 blocks)
    total_blocks_land = 100
    allocated_count = Block.objects.filter(owner__isnull=False).count()
    free_count = total_blocks_land - allocated_count

    context = {
        'grid': grid,
        'status_counts': status_counts,
        'total_blocks': visible_qs.count(),
        'allocated_count': allocated_count,
        'free_count': free_count,
    }
    return render(request, 'farm/dashboard.html', context)


@login_required
def block_detail(request, block_number):
    block = get_object_or_404(Block, block_number=block_number)

    is_superuser = request.user.is_superuser
    is_staff = request.user.is_staff

    # Permission to VIEW: superuser, staff, or the owner of this block
    if not (is_superuser or is_staff):
        owner = _owner_for_user(request.user)
        if owner is None or block.owner_id != owner.id:
            return HttpResponseForbidden("You don't have access to this block.")

    # Permission to EDIT: only superuser or staff
    can_edit = is_superuser or is_staff

    if request.method == 'POST':
        if not can_edit:
            return HttpResponseForbidden("Owners cannot update rows.")

        row_id = request.POST.get('row_id')
        new_status = request.POST.get('status')
        plant_type = request.POST.get('plant_type', '').strip()
        count_per = request.POST.get('count_per_plantation', '').strip()
        yield_per = request.POST.get('yield_per_plantation', '').strip()
        duration = request.POST.get('duration', '').strip()
        rate_raw = request.POST.get('rate', '').strip()

        row = get_object_or_404(Row, id=row_id, block=block)
        was_harvested = (row.status == 'HARVESTED')
        old_status = row.status

        # Apply the updates
        if new_status in dict(Row.STATUS_CHOICES):
            row.status = new_status
        row.plant_type = plant_type
        row.count_per_plantation = count_per
        row.yield_per_plantation = yield_per
        row.duration = duration

        if rate_raw == '':
            row.rate = None
        else:
            from decimal import Decimal, InvalidOperation
            try:
                row.rate = Decimal(rate_raw)
            except (InvalidOperation, ValueError):
                messages.error(request, f'Invalid rate "{rate_raw}" for row {row.row_number}.')
                return redirect('block_detail', block_number=block_number)

        row.save()

        # --- Auto-create a HarvestRecord on transition into HARVESTED ---
        if row.status == 'HARVESTED' and not was_harvested:
            from .models import HarvestRecord
            HarvestRecord.objects.create(
                block=block,
                row_number=row.row_number,
                plant_type=row.plant_type,
                count_per_plantation=row.count_per_plantation,
                yield_per_plantation=row.yield_per_plantation,
                duration=row.duration,
                rate=row.rate,
                revenue=row.revenue_per_plantation,
                seeding_date=row.seeding_date,
                days_to_harvest=days,
                harvested_by=request.user.username,
            )
            messages.success(
                request,
                f'🌾 Row {row.row_number} harvested — history saved!'
            )
        else:
            messages.success(request, f'Row {row.row_number} updated.')

        return redirect('block_detail', block_number=block_number)


        messages.success(request, f'Row {row.row_number} updated.')
        return redirect('block_detail', block_number=block_number)

    rows = block.rows.all().order_by('row_number')
    #from .models import DURATION_CHOICES
    return render(request, 'farm/block_detail.html', {
        'block': block,
        'rows': rows,
        'status_choices': Row.STATUS_CHOICES,
        'duration_choices': DURATION_CHOICES,
        'can_edit': can_edit,
    })
@login_required
def block_history(request, block_number):
    from .models import HarvestRecord
    block = get_object_or_404(Block, block_number=block_number)

    # Permission: superuser, staff, or block owner
    if not (request.user.is_superuser or request.user.is_staff):
        owner = _owner_for_user(request.user)
        if owner is None or block.owner_id != owner.id:
            return HttpResponseForbidden("You don't have access to this block.")

    records = HarvestRecord.objects.filter(block=block)

    total_revenue = sum(float(r.revenue or 0) for r in records)

    return render(request, 'farm/block_history.html', {
        'block': block,
        'records': records,
        'total_revenue': total_revenue,
        'record_count': records.count(),
    })