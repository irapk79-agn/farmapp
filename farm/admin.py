from django.contrib import admin
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django import forms
from django.db import models
from .models import Owner, Block, Row, HarvestRecord, Transaction
@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email')

class RowInline(admin.TabularInline):
    model = Row
    extra = 0
    fields = (
        'row_number', 'plant_type', 'status',
        'count_per_plantation', 'yield_per_plantation', 'rate', 'duration',
        'seeding_date','planted_date', 'harvest_date',
    )
class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 1
    fields = ('date', 'transaction_type', 'amount', 'investment_mode', 'expense_category', 'notes')
@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    # 1. Removed 'amount' and 'investment_mode' here
    list_display = ('block_number', 'owner', 'row_count') 
    
    # 2. Removed 'transaction_type' and 'investment_mode' here
    list_filter = ('owner',) 
    
    search_fields = ('block_number', 'owner__name')
    
    # 3. Added the TransactionInline here
    inlines = [TransactionInline, RowInline] 
    
    save_on_top = True
    change_list_template = "admin/block_changelist.html"
    
    
    
    # 4. Removed the old Financials fieldset
    fieldsets = (
        ('Basic Info', {
            'fields': ('block_number', 'owner', 'notes')
        }),
    )
     
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 3, 'cols': 60})},
    } 
    def row_count(self, obj):
        return obj.rows.count()

@admin.register(Row)
class RowAdmin(admin.ModelAdmin):
    list_display = ('block', 'row_number', 'plant_type', 'status',
                    'count_per_plantation', 'yield_per_plantation',
                    'rate','duration', 'owner_name')
    list_filter = ('status', 'plant_type', 'block__owner')
    list_editable = ('status', 'plant_type')
    search_fields = ('block__block_number', 'plant_type', 'block__owner__name')

    def owner_name(self, obj):
        return obj.block.owner.name if obj.block.owner else '—'
    owner_name.short_description = 'Owner'
   
    def revenue_column(self, obj):
        return obj.revenue_display
    revenue_column.short_description = 'Revenue / Plantation'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(block__owner__name=request.user.username)# Customize admin site header and add a "Back to Portal" link
admin.site.site_header = "Farm Administration"
admin.site.site_title = "Farm Admin"
admin.site.index_title = "Manage Blocks, Rows, and Owners"
admin.site.site_url = "/dashboard/"

@admin.register(HarvestRecord)
class HarvestRecordAdmin(admin.ModelAdmin):
    list_display = ('block', 'row_number', 'plant_type',
                    'seeding_date','yield_per_plantation', 'revenue', 'harvest_date', 'harvested_by')
    list_filter = ('plant_type', 'harvest_date', 'block__owner')
    search_fields = ('plant_type', 'block__block_number', 'harvested_by')
    date_hierarchy = 'harvest_date'

    readonly_fields = ('block', 'row_number', 'plant_type',
                       'count_per_plantation', 'yield_per_plantation',
                       'duration', 'rate', 'revenue',
                       'seeding_date','harvest_date', 'harvested_by', 'receipt' )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False   # read-only log

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

def log_row_update(request, row, message):
        """Logs a change made outside the admin panel into the admin's history."""
        LogEntry.objects.log_action(
          user_id=request.user.pk,
          content_type_id=ContentType.objects.get_for_model(row).pk,
          object_id=row.pk,
          object_repr=str(row),
         action_flag=CHANGE,
         change_message=message
      )