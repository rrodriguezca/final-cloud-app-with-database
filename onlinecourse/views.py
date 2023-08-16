from django.shortcuts import render
from django.http import HttpResponseRedirect
# <HINT> Import any new Models here
from .models import Course, Enrollment, Question, Choice, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging
from django.db.models import Sum
# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.
def submit(request, course_id):

    # Get the current user and the course object
    user = request.user
    course = get_object_or_404(Course, pk=course_id)

    # Get the associated enrollment object
    enrollment = get_object_or_404(Enrollment, user=user, course=course)

    if request.method == 'POST':
        # Create a new submission object referring to the enrollment
        submission = Submission.objects.create(enrollment=enrollment)

        # Collect the selected choices from the HTTP request object
        selected_choice_ids = [int(key.split('_')[1]) for key, value in request.POST.items() if key.startswith('choice_') and value == 'on']
        selected_choices = Choice.objects.filter(pk__in=selected_choice_ids)
        submission.choices.set(selected_choices)

        # Redirect to the show_exam_result view with the submission id to show the exam result
        return redirect('onlinecourse:exam_result', course_id=course_id, submission_id=submission.id)

    # Render the submission form
    return render(request, 'onlinecourse/exam_submission.html', {'course': course})

def extract_answers(request):
    submitted_answers = {}
    questions = Question.objects.all()
    
    for question in questions:
        key = f'question_{question.id}'
        selected_choice_id = int(request.POST.get(key, 0))
        
        correct_choice_id = question.choice_set.filter(is_correct=True).values_list('id', flat=True).first()
        
        submitted_answers[question.id] = {
            'selected_choice_id': selected_choice_id,
            'correct_choice_id': correct_choice_id,
        }
    
    return submitted_answers

def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(Submission, pk=submission_id)

    selected_choice_ids = submission.choices.values_list('id', flat=True)
    total_score = 0
    passing_score = 0

    question_results = []
    for question in course.question_set.all():
        correct_choice_ids = question.choice_set.filter(is_correct=True).values_list('id', flat=True)
        
        # Filter selected choice IDs for the current question

        selected_choice_ids_for_question = [choice_id for choice_id in selected_choice_ids if Choice.objects.get(pk=choice_id).question == question]

        is_correct = set(selected_choice_ids_for_question) == set(correct_choice_ids)

        if is_correct:
            total_score += question.grade_point
        passing_score += question.grade_point

        question_result = {
            'question_text': question.question_text,
            'is_correct': is_correct,
            'correct_choices': correct_choice_ids,
            'selected_choices': selected_choice_ids_for_question,
        }
        question_results.append(question_result)

    passed_exam = total_score >= passing_score

    context = {
        'course': course,
        'question_results': question_results,
        'total_score': total_score,
        'passed_exam': passed_exam,
        'passing_score': passing_score,
    }

    return render(request, 'onlinecourse/exam_result_bootstrap.html', context)

def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    elif request.method == 'POST':
        # Check if user exists
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(username=username, first_name=first_name, last_name=last_name,
                                            password=password)
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    else:
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.id is not None:

        # Check if user enrolled
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView

class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:

        # Create an enrollment
        
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))


