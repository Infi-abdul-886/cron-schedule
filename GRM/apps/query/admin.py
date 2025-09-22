from django.contrib import admin
from .models import QueryFile, QueryTemplate, ScheduledQueryTask, QueryExecutionLog

class QueryTemplateInline(admin.TabularInline):
    model = QueryTemplate
    extra = 0
    fields = ('name', 'description', 'is_active')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(QueryFile)
class QueryFileAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'description', 'get_query_count', 'created_by', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at', 'created_by')
    search_fields = ('file_name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [QueryTemplateInline]
    
    def get_query_count(self, obj):
        return obj.get_query_count()
    get_query_count.short_description = 'Query Count'

@admin.register(QueryTemplate)
class QueryTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'query_file', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at', 'query_file')
    search_fields = ('name', 'description', 'query_file__file_name')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('query_file',)

@admin.register(ScheduledQueryTask)
class ScheduledQueryTaskAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'get_query_templates_count', 'cron_expression', 'output_format', 'is_active', 'last_run')
    list_filter = ('is_active', 'output_format', 'created_at')
    search_fields = ('task_name', 'description')
    readonly_fields = ('last_run', 'created_at', 'updated_at')
    filter_horizontal = ('query_templates',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('task_name', 'description', 'is_active')
        }),
        ('Query Configuration', {
            'fields': ('query_templates',)
        }),
        ('Scheduling', {
            'fields': ('cron_expression',)
        }),
        ('Email Settings', {
            'fields': ('email_recipients', 'email_subject', 'output_format')
        }),
        ('Timestamps', {
            'fields': ('last_run', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_query_templates_count(self, obj):
        return obj.query_templates.count()
    get_query_templates_count.short_description = 'Templates Count'
    
    actions = ['execute_selected_tasks']
    
    def execute_selected_tasks(self, request, queryset):
        from .tasks import execute_scheduled_query_task
        
        executed_count = 0
        for task in queryset.filter(is_active=True):
            execute_scheduled_query_task.delay(task.id)
            executed_count += 1
        
        self.message_user(request, f"Started execution of {executed_count} tasks.")
    execute_selected_tasks.short_description = "Execute selected tasks"

@admin.register(QueryExecutionLog)
class QueryExecutionLogAdmin(admin.ModelAdmin):
    list_display = ('query_template', 'scheduled_task', 'status', 'row_count', 'execution_time', 'executed_at')
    list_filter = ('status', 'executed_at', 'scheduled_task')
    search_fields = ('query_template__name', 'query_template__query_file__file_name', 'scheduled_task__task_name')
    readonly_fields = ('executed_at',)
    list_select_related = ('query_template', 'query_template__query_file', 'scheduled_task')
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically