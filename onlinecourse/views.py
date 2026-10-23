from django.shortcuts import render
from django.http import HttpResponseRedirect
# Import new Models here
from .models import Course, Enrollment, Question, Choice, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging
# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


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


def submit(request, course_id):
    """Create an exam submission record for a course enrollment."""
    user = request.user
    course = get_object_or_404(Course, pk=course_id)
    # Get the enrollment object for the current user and course
    enrollment = get_object_or_404(Enrollment, user=user, course=course)
    # Create a submission object referring to the enrollment
    submission = Submission.objects.create(enrollment=enrollment)
    # Collect the selected choices from exam form
    selected_ids = extract_answers(request)
    # Add each selected choice object to the submission object
    for choice_id in selected_ids:
        choice = get_object_or_404(Choice, pk=choice_id)
        submission.choices.add(choice)
    submission.save()
    # Redirect to show_exam_result with the submission id
    return HttpResponseRedirect(
        reverse(viewname='onlinecourse:show_exam_result', args=(course_id, submission.id))
    )


# An example method to collect the selected choices from the exam form from the request object
def extract_answers(request):
   submitted_anwsers = []
   for key in request.POST:
       if key.startswith('choice'):
           value = request.POST[key]
           choice_id = int(value)
           submitted_anwsers.append(choice_id)
   return submitted_anwsers


def show_exam_result(request, course_id, submission_id):
    """Check if learner passed exam and show their question results."""
    # Get course and submission based on their ids
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(Submission, pk=submission_id)
    # Get the selected choice ids from the submission record
    selected_ids = submission.choices.values_list('id', flat=True)
    # For each question, determine if it was answered correctly
    questions = Question.objects.filter(course=course)
    total_score = 0
    total_grade = 0
    question_results = []

    for question in questions:
        total_grade += question.grade
        # Get all correct choices for this question
        correct_choices = question.choices.filter(is_correct=True).values_list('id', flat=True)
        # Get selected choices for this question
        selected_for_q = [cid for cid in selected_ids if question.choices.filter(id=cid).exists()]
        # Answer is correct if all correct choices are selected and no incorrect ones are selected
        is_correct = (
            set(correct_choices) == set(selected_for_q)
        )
        if is_correct:
            total_score += question.grade

        question_results.append({
            'question': question,
            'is_correct': is_correct,
            'selected_choices': question.choices.filter(id__in=selected_ids),
        })

    # Calculate grade as percentage
    grade = (total_score / total_grade * 100) if total_grade > 0 else 0

    context = {
        'course': course,
        'submission': submission,
        'grade': grade,
        'total_score': total_score,
        'total_grade': total_grade,
        'question_results': question_results,
        'selected_ids': selected_ids,
    }
    return render(request, 'onlinecourse/exam_result_bootstrap.html', context)
