from flask import Blueprint, current_app


bp = Blueprint('user_manager', __name__, url_prefix='/admin/employees')


@bp.route('/manager')
def get_user_manager_page():
    return current_app.send_static_file('html/employee_manager/employee_manager.html')
