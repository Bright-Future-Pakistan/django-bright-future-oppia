# oppia/xapi/views.py
import datetime
import json
import tablib

from django.http import HttpResponse, Http404
from django.template import RequestContext
from django.utils import timezone

from oppia.models import Course, Tracker, Activity
from oppia.quiz.models import Quiz, QuizAttempt

def csv_export(request):
    if not request.user.is_staff:
        raise Http404

    start_date = timezone.now() - datetime.timedelta(days=7)
    end_date = timezone.now()
    
    headers = ('user_id', 
               'course_id', 
               'course_title',
               'attempt_date', 
               'submitted_date', 
               'type', 
               'quiz_id', 
               'quiz_title', 
               'section_title',
               'completed',
               'time_taken',
               'score',
               'maxscore')
    
    data = []
    data = tablib.Dataset(*data, headers=headers)
    
    trackers = Tracker.objects.filter(submitted_date__gte=start_date, submitted_date__lte=end_date, type=Activity.QUIZ)
    
    for tracker in trackers:
        # Get the matching quiz attempt object
        tracker_data = json.loads(tracker.data)
        quiz_instance = tracker_data['instance_id']
        
        try:
            quiz_attempt = QuizAttempt.objects.get(instance_id = quiz_instance)
        except QuizAttempt.DoesNotExist:
            continue
        
        data.append(
                    (
                       tracker.user.id, 
                       tracker.course.id, 
                       tracker.course.title,
                       quiz_attempt.attempt_date, 
                       tracker.submitted_date, 
                       tracker.type, 
                       quiz_attempt.quiz.id, 
                       quiz_attempt.quiz.title, 
                       tracker.section_title,
                       tracker.completed,
                       tracker.time_taken,
                       quiz_attempt.score,
                       quiz_attempt.maxscore
                    )
                )
    
    response = HttpResponse(data.csv, content_type='application/text;charset=utf-8')
    response['Content-Disposition'] = "attachment; filename=xapi-export.csv" 

    return response