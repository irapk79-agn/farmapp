from django.contrib import admin
from .models import Owner, Block, Row
from .models import Owner, Block, Row, HarvestRecord

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
@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('block_number', 'owner','amount', 'investment_mode', 'row_count')
    list_filter = ('owner', 'transaction_type', 'investment_mode')
    search_fields = ('block_number', 'owner__name')
    inlines = [RowInline]
    save_on_top = True
    #actions = [assign_owner_action]
    change_list_template = "admin/block_changelist.html" 
   
     # Show the new financial fields in the edit form
    fieldsets = (
        ('Basic Info', {
            'fields': ('block_number', 'owner', 'notes')
        }),
        ('Financials', {
            'fields': ('amount', 'transaction_type', 'investment_mode', 'expense_category'),
            'description': "Enter the transaction details. If it's an expense, select a category."
        }),
    )

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