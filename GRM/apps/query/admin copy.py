# GRM/apps/cronjob/admin.py - CORRECT VERSION

# from django.contrib import admin
# from .models import ScheduledJob

# @admin.register(ScheduledJob)
# class ScheduledJobAdmin(admin.ModelAdmin):
#     list_display = ('job_name', 'cron_schedule', 'is_enabled', 'last_run')
#     list_filter = ('is_enabled',)
#     search_fields = ('job_name', 'job_func')

# This file can be empty.
# The django-apscheduler models are registered automatically by the package.
# apps/cronjob/admin.py
from django.contrib import admin
from celery.app.control import Control
from celery import current_app   # ✅ instead of celery.task.control
from .models import JobProgress, TaskLog, ScheduledTask
from .tasks import process_data_task
from .tasks import trigger_admin_notification_view
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect

control = Control(app=current_app)


class TaskLogInline(admin.TabularInline):
    model = TaskLog
    extra = 0
    readonly_fields = ('task_id', 'message', 'status', 'created_at')
    can_delete = False

@admin.register(JobProgress)
class JobProgressAdmin(admin.ModelAdmin):
    list_display = (
        'job_id', 'status', 'progress_percent', 'task_id',
        'last_step', 'last_processed_line', 'updated_at', 'actions_column'
    )
    readonly_fields = ('task_id', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('job_id',)
    inlines = [TaskLogInline]

    def actions_column(self, obj):
        # ✅ FIX: Corrected the URL names to match Django's admin pattern
        return format_html(
            '<a class="button" href="{}">Resume</a>&nbsp;'
            '<a class="button" href="{}">Restart</a>&nbsp;'
            '<a class="button" href="{}">Terminate</a>',
            reverse("admin:cronjob_jobprogress_resume", args=[obj.pk]),
            reverse("admin:cronjob_jobprogress_restart", args=[obj.pk]),
            reverse("admin:cronjob_jobprogress_terminate", args=[obj.pk]),
        )
    actions_column.short_description = "Actions"

    def get_urls(self):
        urls = super().get_urls()
        # ✅ FIX: Corrected the names to be unique
        custom_urls = [
            path('<int:pk>/resume/', self.admin_site.admin_view(self.resume_job_view), name="cronjob_jobprogress_resume"),
            path('<int:pk>/restart/', self.admin_site.admin_view(self.restart_job_view), name="cronjob_jobprogress_restart"),
            path('<int:pk>/terminate/', self.admin_site.admin_view(self.terminate_job_view), name="cronjob_jobprogress_terminate"),
        ]
        return custom_urls + urls

    # ✅ NEW: Helper function to find the correct task to run
    def _get_task_path_for_job(self, job):
        try:
            return ScheduledTask.objects.get(job=job).task_path
        except ScheduledTask.DoesNotExist:
            return None

    # ✅ FIX: Made resume logic dynamic
    def resume_job_view(self, request, pk):
        job = JobProgress.objects.get(pk=pk)
        task_path = self._get_task_path_for_job(job)
        if job.status != 'RUNNING' and task_path:
            current_app.send_task(task_path, args=[job.job_id])
            self.message_user(request, f"Resumed job {job.job_id}.")
        else:
            self.message_user(request, f"Could not resume job {job.job_id}: No scheduled task found.", level='ERROR')
        return redirect(request.META.get('HTTP_REFERER', 'admin:index'))

    # ✅ FIX: Made restart logic dynamic and complete
    def restart_job_view(self, request, pk):
        job = JobProgress.objects.get(pk=pk)
        task_path = self._get_task_path_for_job(job)
        if task_path:
            job.last_step = None
            job.checkpoint_data = None
            job.last_processed_line = 0
            job.total_lines = 0
            job.progress_percent = 0
            job.status = 'PENDING'
            job.save()
            current_app.send_task(task_path, args=[job.job_id])
            self.message_user(request, f"Restarted job {job.job_id} from scratch.")
        else:
            self.message_user(request, f"Could not restart job {job.job_id}: No scheduled task found.", level='ERROR')
        return redirect(request.META.get('HTTP_REFERER', 'admin:index'))

    def terminate_job_view(self, request, pk):
        job = JobProgress.objects.get(pk=pk)
        if job.task_id:
            current_app.control.revoke(job.task_id, terminate=True, signal='SIGTERM')
            job.status = 'TERMINATED'
            job.save()
            self.message_user(request, f"Terminated job {job.job_id}.")
        return redirect(request.META.get('HTTP_REFERER', 'admin:index'))

@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    # This is now correct
    list_display = ('job', 'task_path', 'get_schedule', 'enabled')
    list_filter = ('enabled',)
    search_fields = ('job__job_id', 'task_path')

    def get_schedule(self, obj):
        if obj.crontab: return str(obj.crontab)
        if obj.interval: return str(obj.interval)
        return "No schedule set"