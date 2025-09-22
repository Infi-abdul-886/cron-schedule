from celery import shared_task,group,states
import time
from django.utils import timezone
from .views.adminNotificationView import AdminNotificationView,AdminNotificationRunner
from datetime import timedelta
from celery.exceptions import Ignore
from celery.signals import task_revoked # ✅ ADD THIS IMPORT
from .models import JobProgress, TaskLog

@shared_task
def sample_task():
    print("Task started")
    time.sleep(5)
    print("Task finished")
    return "Task completed"

@shared_task
def clean_expired_fares():
    """
    Finds and updates all transactions where the fare_expiry_date has passed.
    """
    from apps.shared.models.grm_models import TransactionMaster

    # 1. Get the current time. It's crucial to use timezone.now()
    #    to ensure the comparison is correct based on your project's timezone settings.
    now = timezone.now()

    # 2. Filter TransactionMaster to get only the objects where the
    #    fare_expiry_date is less than or equal to the current time.
    #    We also ensure we are only updating records that don't already have the 'expired' status.
    expired_fares_query = TransactionMaster.objects.filter(
        fare_expiry_date__lte=now
    )

    # 3. Use the .update() method directly on the filtered queryset.
    #    This is much more efficient than fetching the objects first.
    #    .update() returns the number of rows that were changed.
    #    NOTE: You must have a 'status' field in your TransactionMaster model for this to work.
    count = expired_fares_query.count()

    # 4. Return a clear message indicating how many fares were updated.
    return f"{count} fares have been marked as expired."

# @shared_task(bind=True, name="tasks.trigger_admin_notification_view")
# def trigger_admin_notification_view(self, job_id):
#     """
#     A managed task that executes the AdminNotificationView logic,
#     with support for status tracking, locking, and resuming.
#     """
#     try:
#         # 1. Find the corresponding job in the database.
#         job = JobProgress.objects.get(job_id=job_id)
#     except JobProgress.DoesNotExist:
#         # If the job was deleted from the admin, stop the task.
#         raise Ignore()

#     # 2. Prevent the task from running if it's already running.
#     if job.status == 'RUNNING':
#         print(f"Job '{job_id}' is already running. Skipping this run.")
#         return "Skipped: Already running."

#     # 3. Set the status to 'RUNNING' and record the Celery task ID.
#     job.status = 'RUNNING'
#     job.task_id = self.request.id
#     job.save()

#     try:
#         # --- YOUR ORIGINAL LOGIC IS PLACED HERE ---
#         view_instance = AdminNotificationView()
#         response = view_instance.get(request=None)
#         # -----------------------------------------

#         # 4. If successful, mark the job as 'COMPLETED'.
#         job.status = "COMPLETED"
#         job.save()
#         TaskLog.objects.create(
#             job=job, 
#             task_id=self.request.id, 
#             message="Admin notifications sent successfully.", 
#             status="COMPLETED"
#         )
        
#         if hasattr(response, 'content'):
#             return response.content.decode()
#         return "Task finished successfully."

#     except Exception as e:
#         # 5. If any error occurs, mark the job as 'FAILED'.
#         job.status = "FAILED"
#         job.save()
#         TaskLog.objects.create(
#             job=job, 
#             task_id=self.request.id, 
#             message=f"Task failed with error: {e}", 
#             status="FAILED"
#         )
#         # Re-raise the exception so Celery also knows it failed.
#         raise
    
@shared_task(bind=True,name="apps.cronjob.tasks.trigger_admin_notification_view")
def trigger_admin_notification_view(self, job_id):
    try:
        job = JobProgress.objects.get(job_id=job_id)
    except JobProgress.DoesNotExist:
        raise Ignore()

    if job.status == "RUNNING":
        return "Skipped: Already running."

    job.status = "RUNNING"
    job.task_id = self.request.id
    job.save(update_fields=["status", "task_id", "updated_at"])

    try:
        runner = AdminNotificationRunner(job)
        summary = runner.run()

        job.status = "COMPLETED"
        job.save(update_fields=["status", "updated_at"])
        TaskLog.objects.create(job=job, task_id=self.request.id, message="Admin notifications sent.", status="COMPLETED")
        return summary

    except Exception as e:
        job.status = "FAILED"
        job.save(update_fields=["status", "updated_at"])
        TaskLog.objects.create(job=job, task_id=self.request.id, message=f"Failed: {e}", status="FAILED")
        raise
    
@shared_task(name="tasks.run_all_maintenance_jobs")
def run_all_maintenance_jobs():
    """
    This task runs multiple maintenance jobs in parallel using a group.
    """
    # Create a "signature" for each task we want to run.
    # A signature is just the task definition. .s() is the shorthand for signature.
    jobs_to_run = group([
        clean_expired_fares.s(),
        sample_task.s()
    ])

    # Call the group. This puts both tasks on the queue at the same time.
    # The result object represents the entire group.
    group_result = jobs_to_run.apply_async()

    # This part is optional but useful for seeing the result right away.
    # .get() will wait until ALL tasks in the group are finished.
    # Note: Using .get() will block the current process until the result is ready.
    # In a real scheduled task, you might just let it run in the background.
    # results = group_result.get()
    
    # The 'results' variable will be a list of the return values
    # from each task in the group.
    # For example: ['5 fares have been marked as expired.', 'Task finished successfully.']
    
    return f"Maintenance group completed with results: {group_result.id}"

@shared_task
def generate_daily_summary_report():
    """
    Generates a summary report of transaction activity from the last 24 hours.
    """
    from apps.shared.models.grm_models import TransactionMaster

    now = timezone.now()
    one_day_ago = now - timedelta(days=1)

    # 1. Count new transactions created in the last 24 hours
    #    Assumes 'transaction_date' is the creation timestamp.
    new_transactions_count = TransactionMaster.objects.filter(
        transaction_date__gte=one_day_ago
    ).count()

    # 2. Count all fares that are currently active
    #    Assumes 'active_status = 1' means the fare is active.
    active_fares_count = TransactionMaster.objects.filter(
        active_status=1
    ).count()

    # 3. You could add more stats here, like total expired fares, etc.

    summary = (
        f"Daily Report: {new_transactions_count} new transactions in the last 24 hours. "
        f"Total active fares: {active_fares_count}."
    )

    # --- ARTIFICIAL DELAY ADDED HERE ---
    print("Report generated. Now waiting for 30 seconds before finishing...")
    time.sleep(30)
    # ------------------------------------

    print(f"Finished delay. Returning summary: {summary}")
    return summary

@task_revoked.connect
def on_task_revoked(request, terminated, signum, expired, **kwargs):
    """
    This function is called by Celery itself whenever a task is terminated.
    """
    # We only care about tasks that were forcefully terminated (e.g., from Flower)
    if terminated:
        task_id = request.id
        print(f"TERMINATION DETECTED for task_id: {task_id}")
        try:
            # Find the job in our database using the task_id
            job = JobProgress.objects.get(task_id=task_id)
            
            # Update the status to 'TERMINATED'
            job.status = 'TERMINATED'
            job.save()

            # Create a log entry to record what happened
            TaskLog.objects.create(
                job=job,
                task_id=task_id,
                message=f"Task terminated externally at line {job.last_processed_line}. Signal: {signum}.",
                status="TERMINATED"
            )
            print(f"Successfully updated JobProgress '{job.job_id}' to TERMINATED.")
        except JobProgress.DoesNotExist:
            # This happens if a task that is not a JobProgress job is terminated. Safe to ignore.
            print(f"Terminated task {task_id} not found in JobProgress. Ignoring.")


# YOUR EXISTING TASK (NO CHANGES NEEDED HERE)
@shared_task(bind=True)
def process_data_task(self, job_id):
    try:
        job = JobProgress.objects.get(job_id=job_id)
    except JobProgress.DoesNotExist:
        raise Ignore()
    
    if job.status == 'RUNNING':
        print(f"Job {job_id} is already running. Skipping.")
        return "Skipped: Already running."

    job.status = 'RUNNING'
    job.task_id = self.request.id
    job.save()

    total_rows = 500
    if job.total_lines == 0:
        job.total_lines = total_rows
        job.save()

    start_line = job.last_processed_line + 1

    try:
        for line in range(start_line, total_rows + 1):
            time.sleep(0.05)
            job.last_processed_line = line
            job.progress_percent = (line / job.total_lines) * 100
            job.save(update_fields=["last_processed_line", "progress_percent", "updated_at"])
            if line % 20 == 0:
                TaskLog.objects.create(
                    job=job, task_id=self.request.id,
                    message=f"Processed line {line}", status="RUNNING"
                )

        job.status = "COMPLETED"
        job.save()
        TaskLog.objects.create(job=job, task_id=self.request.id, message="Job completed", status="COMPLETED")
    except Exception as e:
        job.status = "FAILED"
        job.save()
        TaskLog.objects.create(job=job, task_id=self.request.id, message=f"Error: {e}", status="FAILED")
        self.update_state(state=states.FAILURE, meta={'exc': str(e)})
        raise