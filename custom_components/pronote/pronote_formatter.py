"""Data Formatter for the Pronote integration."""

import logging

from .const import (
    HOMEWORK_DESC_MAX_LENGTH,
)

_LOGGER = logging.getLogger(__name__)

def format_displayed_lesson(lesson):
    if lesson.detention is True:
        return 'RETENUE'
    if lesson.subject:
        return lesson.subject.name
    return 'autre'

def format_lesson(lesson):
    return {
        'start_at': lesson.start,
        'end_at': lesson.end,
        'start_time': lesson.start.strftime("%H:%M"),
        'end_time': lesson.end.strftime("%H:%M"),
        'lesson': format_displayed_lesson(lesson),
        'classroom': lesson.classroom,
        'canceled': lesson.canceled,
        'status': lesson.status,
        'background_color': lesson.background_color,
        'teacher_name': lesson.teacher_name,
        'teacher_names': lesson.teacher_names,
        'classrooms': lesson.classrooms,
        'outing': lesson.outing,
        'memo': lesson.memo,
        'group_name': lesson.group_name,
        'group_names': lesson.group_names,
        'exempted': lesson.exempted,
        'virtual_classrooms': lesson.virtual_classrooms,
        'num': lesson.num,
        'detention': lesson.detention,
        'test': lesson.test,
    }

def format_attachment_list(attachments):
    return [{
        'name': attachment.name,
        'url': attachment.url,
        'type': attachment.type,
    } for attachment in attachments]

def format_homework(homework) -> dict:
    return {
        'date': homework.date,
        'subject': homework.subject.name,
        'short_description': (homework.description)[0:HOMEWORK_DESC_MAX_LENGTH],
        'description': (homework.description),
        'done': homework.done,
        'background_color': homework.background_color,
        'files': format_attachment_list(homework.files),
    }

def format_grade(grade) -> dict:
    return {
        'date': grade.date,
        'subject': grade.subject.name,
        'comment': grade.comment,
        'grade': grade.grade,
        'out_of': str(grade.out_of).replace('.',','),
        'default_out_of': str(grade.default_out_of).replace('.',','),
        'grade_out_of': grade.grade + '/' + grade.out_of,
        'coefficient': str(grade.coefficient).replace('.',','),
        'class_average': str(grade.average).replace('.',','),
        'max': str(grade.max).replace('.',','),
        'min': str(grade.min).replace('.',','),
        'is_bonus': grade.is_bonus,
        'is_optionnal': grade.is_optionnal,
        'is_out_of_20': grade.is_out_of_20,
    }

def format_absence(absence) -> dict:
    return {
        'from': absence.from_date,
        'to': absence.to_date,
        'justified': absence.justified,
        'hours': absence.hours,
        'days': absence.days,
        'reason': str(absence.reasons)[2:-2],
    }

def format_delay(delay) -> dict:
    return {
        'date': delay.date,
        'minutes': delay.minutes,
        'justified': delay.justified,
        'justification': delay.justification,
        'reasons': str(delay.reasons)[2:-2],
    }

def format_evaluation(evaluation) -> dict:
    return {
        'name': evaluation.name,
        'domain': evaluation.domain,
        'date': evaluation.date,
        'subject': evaluation.subject.name,
        'description': evaluation.description,
        'coefficient': evaluation.coefficient,
        'paliers': evaluation.paliers,
        'teacher': evaluation.teacher,
        'acquisitions': [
            {
                'order': acquisition.order,
                'name_id': acquisition.name_id,
                'name': acquisition.name,
                'abbreviation': acquisition.abbreviation,
                'level': acquisition.level,
                'domain_id': acquisition.domain_id,
                'domain': acquisition.domain,
                'coefficient': acquisition.coefficient,
                'pillar_id': acquisition.pillar_id,
                'pillar': acquisition.pillar,
                'pillar_prefix': acquisition.pillar_prefix,
            }
            for acquisition in evaluation.acquisitions
        ]
    }

def format_average(average) -> dict:
    return {
        'average': average.student,
        'class': average.class_average,
        'max': average.max,
        'min': average.min,
        'out_of': average.out_of,
        'default_out_of': average.default_out_of,
        'subject': average.subject.name,
        'background_color': average.background_color,
    }

def format_punishment(punishment) -> dict:
    return {
        'date': punishment.given.strftime("%Y-%m-%d"),
        'subject': punishment.during_lesson,
        'reasons': punishment.reasons,
        'circumstances': punishment.circumstances,
        'nature': punishment.nature,
        'duration': str(punishment.duration),
        'homework': punishment.homework,
        'exclusion': punishment.exclusion,
        'during_lesson': punishment.during_lesson,
        'homework_documents': format_attachment_list(punishment.homework_documents),
        'circumstance_documents': format_attachment_list(punishment.circumstance_documents),
        'giver': punishment.giver,
        'schedule': [{
            'start': schedule.start,
            'duration': schedule.duration,
        } for schedule in punishment.schedule],
        'schedulable': punishment.schedulable,
    }

def format_food_list(food_list) -> dict:
    formatted_food_list = []
    if food_list is None:
        return formatted_food_list

    for food in food_list:
        formatted_food_labels = []
        for label in food.labels:
            formatted_food_labels.append({
                'name': label.name,
                'color': label.color,
            })
        formatted_food_list.append({
            'name': food.name,
            'labels': formatted_food_labels,
        })

    return formatted_food_list

def format_menu(menu) -> dict:
    return {
        'name': menu.name,
        'date': menu.date.strftime("%Y-%m-%d"),
        'is_lunch': menu.is_lunch,
        'is_dinner': menu.is_dinner,
        'first_meal': format_food_list(menu.first_meal),
        'main_meal': format_food_list(menu.main_meal),
        'side_meal': format_food_list(menu.side_meal),
        'other_meal': format_food_list(menu.other_meal),
        'cheese': format_food_list(menu.cheese),
        'dessert': format_food_list(menu.dessert),
    }

def format_information_and_survey(information_and_survey) -> dict:
    return {
        'author': information_and_survey.author,
        'title': information_and_survey.title,
        'read': information_and_survey.read,
        'creation_date': information_and_survey.creation_date,
        'start_date': information_and_survey.start_date,
        'end_date': information_and_survey.end_date,
        'category': information_and_survey.category,
        'survey': information_and_survey.survey,
        'anonymous_response': information_and_survey.anonymous_response,
        'attachments': format_attachment_list(information_and_survey.attachments),
        'template': information_and_survey.template,
        'shared_template': information_and_survey.shared_template,
        'content': information_and_survey.content,
    }