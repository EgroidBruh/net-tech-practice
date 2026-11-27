from sqladmin import Admin, ModelView

from database import SessionLocal
from models.tables import (
    DefaultDutyRow, EmployeeRow, IncidentEventRow, IncidentRow, ShiftRow, NotificationRow,
)


class ReadOnlyView(ModelView):
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    column_list = "__all__"
    column_details_list = "__all__"
    page_size = 25


class EmployeeAdmin(ReadOnlyView, model=EmployeeRow):
    name = "Сотрудник"
    name_plural = "Сотрудники"
    column_searchable_list = [EmployeeRow.last_name, EmployeeRow.first_name, EmployeeRow.email]
    column_sortable_list = [EmployeeRow.last_name, EmployeeRow.created_at]


class ShiftAdmin(ReadOnlyView, model=ShiftRow):
    name = "Смена"
    name_plural = "Смены"
    column_sortable_list = [ShiftRow.start_time, ShiftRow.end_time]


class DefaultDutyAdmin(ReadOnlyView, model=DefaultDutyRow):
    name = "Дежурный по умолчанию"
    name_plural = "Дежурный по умолчанию"


class IncidentAdmin(ReadOnlyView, model=IncidentRow):
    name = "Инцидент"
    name_plural = "Инциденты"
    column_searchable_list = [IncidentRow.title, IncidentRow.source, IncidentRow.error_code]
    column_sortable_list = [IncidentRow.created_at, IncidentRow.severity, IncidentRow.status]


class IncidentEventAdmin(ReadOnlyView, model=IncidentEventRow):
    name = "Событие инцидента"
    name_plural = "События инцидентов"
    column_sortable_list = [IncidentEventRow.occurred_at]


class NotificationAdmin(ReadOnlyView, model=NotificationRow):
    name = "Телефонное оповещение"
    name_plural = "Телефонные оповещения"
    column_sortable_list = [NotificationRow.created_at, NotificationRow.status]


def setup_admin(app, session_maker=SessionLocal):
    admin = Admin(app, session_maker=session_maker, title="Таблицы БД")
    for view in (EmployeeAdmin, ShiftAdmin, DefaultDutyAdmin, IncidentAdmin, IncidentEventAdmin, NotificationAdmin):
        admin.add_view(view)
    return admin
