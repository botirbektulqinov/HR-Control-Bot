from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    waiting_jshshir = State()


class Punch(StatesGroup):
    waiting_location_in = State()
    waiting_location_out = State()


class AdminFlow(StatesGroup):
    report_range = State()
    reset_jshshir = State()
    addhr_jshshir = State()
    add_emp_name = State()
    add_emp_jshshir = State()
    add_emp_dept = State()
