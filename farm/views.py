from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import Block, Row, DURATION_CHOICES
from datetime import date, timedelta
from calendar import Calendar
from django.db.models import Sum, Count


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
        block_numbers = list(range(1, 101))  
    else:
        owner = _owner_for_user(request.user)
        if owner is None:
            visible_blocks = {}
            block_numbers = [] # No owner, no blocks
            
        else:
            qs = Block.objects.filter(owner=owner).prefetch_related('rows')
            visible_blocks = {b.block_number: b for b in qs}
            block_numbers = [b.block_number for b in qs]   # Owners ONLY see their block numbers

    grid = []
    for n in block_numbers:
        block = visible_blocks.get(n)
        state = None
        if block is not None:
            if block.owner_id:
                state = 'allocated'
            else:
                active = block.rows.exclude(status='PLOWING').exists()
                state = 'cultivating' if active else 'free'  
        grid.append((n, block, state))

    total_blocks_land = 100
    allocated_count = Block.objects.filter(owner__isnull=False).count()
    free_count = total_blocks_land - allocated_count
    cultivating_unowned = sum(1 for _, b, s in grid if s == 'cultivating')

    visible_qs = Block.objects.filter(block_number__in=[n for n, b, _ in grid if b])
    rows_qs = Row.objects.filter(block__in=visible_qs)
    
    status_counts = {
        'PLOWING': rows_qs.filter(status='PLOWING').count(),
        'SEEDING': rows_qs.filter(status='SEEDING').count(),
        'WATERING': rows_qs.filter(status='WATERING').count(),
        'READY_TO_HARVEST': rows_qs.filter(status='READY_TO_HARVEST').count(),
        'HARVESTED': rows_qs.filter(status='HARVESTED').count(),
    }

    # ==========================================
    # NEW FINANCIAL LOGIC
    # ==========================================
    from .models import HarvestRecord
    harvests = HarvestRecord.objects.filter(block__in=visible_qs).order_by('-harvest_date')
    
    total_funding = sum(float(b.amount or 0) for b in visible_qs if b.transaction_type == 'FUNDING')
    total_expenses = sum(float(b.amount or 0) for b in visible_qs if b.transaction_type == 'EXPENSE')
    total_returns = sum(float(h.revenue or 0) for h in harvests)
    
    is_admin = request.user.is_superuser or request.user.is_staff

    if is_admin:
        # Farm Manager View: Profit = Funding - Expenses (Returns are ignored)
        net_profit = total_funding - total_expenses
    else:
        # Owner View: Profit = Harvest Returns - Funding (Expenses are ignored, they are farm's responsibility)
        net_profit = total_returns - total_funding

    transactions = []
    
    # Add Funding & Expenses
    for b in visible_qs:
        if b.amount and b.amount > 0:
            mode = b.get_investment_mode_display() or "Unknown"
            
            if b.transaction_type == 'EXPENSE':
                cat = b.get_expense_category_display() or "General"
                desc = f"{cat} paid via {mode}"
                amount = -float(b.amount) 
                is_income = False
            else:
                desc = f"Funding received via {mode}"
                amount = float(b.amount)   
                is_income = True

            transactions.append({
                'date': None, 
                'block': b.block_number,
                'owner_name': b.owner.name if b.owner else '—',
                'description': desc,
                'amount': amount,
                'is_income': is_income,                    
                'is_funding': (b.transaction_type == 'FUNDING'), 
                'is_expense': (b.transaction_type == 'EXPENSE'),                  
            })
            
    # Add Harvests
    for h in harvests:
        if h.revenue and h.revenue > 0:
            transactions.append({
                'date': h.harvest_date,
                'block': h.block.block_number,
                'owner_name': h.block.owner.name if h.block.owner else '—',
                'description': f"{h.plant_type} (Row {h.row_number})",
                'amount': float(h.revenue),
                'is_income': True,
                'is_funding': False,
                'is_expense': False,
            })
            
    # Sort: Newest dates first. (Investments have date=None so they go to the top)
    transactions.sort(key=lambda x: (str(x['date']), x['is_income']), reverse=True)
    # ==========================================

    context = {
        'grid': grid,
        'status_counts': status_counts,
        'total_blocks': visible_qs.count(),
        'allocated_count': allocated_count,
        'free_count': free_count,
        'cultivating_unowned': cultivating_unowned,
        
        # Pass the financial variables to the template
        'total_funding': total_funding,
        'total_expenses': total_expenses,
        'total_returns': total_returns,
        'net_profit': net_profit,
        'transactions': transactions,
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
        if row.status == 'HARVESTED' and old_status != 'HARVESTED':
            messages.success(request, f'🌾 Row {row.row_number} harvested — history saved!')
        else:
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

    is_staff_or_admin = request.user.is_superuser or request.user.is_staff
    # Permission: superuser, staff, or block owner
    if not (request.user.is_superuser or request.user.is_staff):
        owner = _owner_for_user(request.user)
        if owner is None or block.owner_id != owner.id:
            return HttpResponseForbidden("You don't have access to this block.")

    # Handle file upload
    if request.method == 'POST':
        if not is_staff_or_admin:
            return HttpResponseForbidden("Only staff can upload receipts.")
        
        record_id = request.POST.get('record_id')
        record = get_object_or_404(HarvestRecord, id=record_id, block=block)
       
        
        
        if request.FILES.get('receipt'):
            record.receipt = request.FILES['receipt']
            record.save()
            messages.success(request, 'Receipt uploaded successfully!')
        else:
            messages.error(request, 'No file selected.')

        return redirect('block_history', block_number=block_number)


    records = HarvestRecord.objects.filter(block=block)

    total_revenue = sum(float(r.revenue or 0) for r in records)

    return render(request, 'farm/block_history.html', {
        'block': block,
        'records': records,
        'total_revenue': total_revenue,
        'record_count': records.count(),
        'can_edit': is_staff_or_admin,
    })
@login_required
def harvest_calendar(request):
    from .models import HarvestRecord

    # Parse year/month from URL or default to today
    today = date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not (1 <= month <= 12):
            raise ValueError
    except (ValueError, TypeError):
        year, month = today.year, today.month

    # Determine which blocks this user can see
    if request.user.is_superuser or request.user.is_staff:
        visible_blocks = Block.objects.all()
    else:
        owner = _owner_for_user(request.user)
        visible_blocks = Block.objects.filter(owner=owner) if owner else Block.objects.none()

    # Pull harvests for the visible month
    records = HarvestRecord.objects.filter(
        block__in=visible_blocks,
        harvest_date__year=year,
        harvest_date__month=month,
    ).order_by('harvest_date', 'block__block_number', 'row_number')

    # Group records by day
    records_by_day = {}
    for rec in records:
        records_by_day.setdefault(rec.harvest_date.day, []).append(rec)

    # Build the calendar grid (weeks of days, Mon=0 ... Sun=6)
    cal = Calendar(firstweekday=0)  # 0 = Monday
    month_days = cal.monthdayscalendar(year, month)

    # Month totals
    month_total_records = records.count()
    month_total_revenue = sum(float(r.revenue or 0) for r in records)

    # Prev / next month navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    context = {
        'year': year,
        'month': month,
        'month_name': date(year, month, 1).strftime('%B %Y'),
        'month_days': month_days,
        'records_by_day': records_by_day,
        'month_total_records': month_total_records,
        'month_total_revenue': month_total_revenue,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'today_day': today.day if (today.year == year and today.month == month) else None,
    }
    return render(request, 'farm/harvest_calendar.html', context)