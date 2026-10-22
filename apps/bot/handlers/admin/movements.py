from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from ...utils.db import (
    is_admin, get_all_devices, get_all_employees_with_dept,
    change_device_responsible, get_device_data, get_all_departments,
    create_employee, can_manage_device,
    # send_movement_card_to_print,
)
from ...keyboards.inline import departments_keyboard, confirm_keyboard, cancel_keyboard
from .common import back_to_main_menu, MoveDeviceStates, NewEmployeeMoveStates

router = Router()


def movement_result(movement):
    text = (
        "✅ Ответственный изменён.\n\n"
        f"Техника: {movement['device'].name}\n"
        f"Инвентарник: {movement['device'].inventory_number}\n"
        f"Ответственный: {movement['from_responsible']} → {movement['to_responsible']}"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
    return text, kb.as_markup()


@router.callback_query(F.data == "admin_move_device_menu")
async def move_device_menu(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    devices = await get_all_devices(callback.from_user.id)
    if not devices:
        await callback.message.edit_text("Нет техники для изменения ответственного.")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for device in devices[:20]:
        kb.row(InlineKeyboardButton(
            text=f"{device.inventory_number} – {device.name[:30]}",
            callback_data=f"move_dev_{device.id}"
        ))
    kb.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main"))
    await callback.message.edit_text("Выберите технику для создания карточки перемещения (смена ответственного):", reply_markup=kb.as_markup())
    await state.set_state(MoveDeviceStates.waiting_for_device)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^move_dev_\d+$"))
async def select_device_for_move(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    device_id = int(callback.data.split("_")[-1])
    device = await get_device_data(device_id, callback.from_user.id)
    if not device:
        await callback.message.edit_text("Устройство не найдено или нет доступа.")
        await callback.answer()
        return

    # только подразделения организации, к которой относится оборудование
    departments = await get_all_departments(callback.from_user.id, organization_id=device.organization_id)
    if not departments:
        await callback.message.edit_text("В организации оборудования нет подразделений.")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for dept in departments[:40]:
        kb.row(InlineKeyboardButton(text=dept.name, callback_data=f"move_dept_{dept.id}"))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    await state.clear()
    await state.update_data(device_id=device_id)
    await callback.message.edit_text(
        f"Техника: {device.inventory_number} – {device.name}\n"
        f"Организация: {device.organization.code} {device.organization.name}\n\n"
        f"Выберите подразделение нового ответственного:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(MoveDeviceStates.waiting_for_employee)
    await callback.answer()


@router.callback_query(MoveDeviceStates.waiting_for_employee, F.data.startswith("move_dept_"))
async def select_department_for_employee(callback: CallbackQuery, state: FSMContext):
    dept_id = int(callback.data.split("_")[-1])
    await state.update_data(department_id=dept_id)
    employees = [e for e in await get_all_employees_with_dept(callback.from_user.id, department_id=dept_id)
                 if e.active]

    data = await state.get_data()
    kb = InlineKeyboardBuilder()
    for emp in employees[:40]:
        kb.row(InlineKeyboardButton(text=emp.full_name, callback_data=f"move_emp_{emp.id}"))
    kb.row(InlineKeyboardButton(text="👤➕ Создать сотрудника",
                                callback_data=f"qr_newemp_{data.get('device_id')}"))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    text = "Выберите нового ответственного:" if employees else "В этом подразделении нет активных сотрудников."
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(MoveDeviceStates.waiting_for_employee, F.data.startswith("move_emp_"))
async def set_new_responsible(callback: CallbackQuery, state: FSMContext):
    employee_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    device_id = data.get('device_id')

    success, msg, movement = await change_device_responsible(device_id, employee_id, callback.from_user.id)
    if success and movement:
        text, kb = movement_result(movement)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
    else:
        await callback.message.edit_text(f"❌ {msg}")
        await back_to_main_menu(callback, callback.from_user.id)

    await state.clear()


# ---------- Создать сотрудника и переместить оборудование ----------
@router.callback_query(F.data.regexp(r"^qr_newemp_\d+$"))
async def new_employee_move_start(callback: CallbackQuery, state: FSMContext):
    device_id = int(callback.data.split("_")[-1])
    if not await can_manage_device(callback.from_user.id, device_id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    device = await get_device_data(device_id, callback.from_user.id)
    await state.clear()
    await state.update_data(device_id=device_id, organization_id=device.organization_id)
    await callback.message.edit_text(
        f"Техника: {device.inventory_number} – {device.name}\n"
        f"Организация: {device.organization.code} {device.organization.name}\n\n"
        "Введите ФИО нового сотрудника:",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(NewEmployeeMoveStates.waiting_for_fullname)
    await callback.answer()


@router.message(NewEmployeeMoveStates.waiting_for_fullname)
async def new_employee_move_fullname(message: Message, state: FSMContext):
    full_name = (message.text or "").strip()
    if len(full_name) < 3:
        await message.answer("Слишком короткое имя. Введите ФИО полностью.", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    departments = await get_all_departments(message.from_user.id, organization_id=data["organization_id"])
    if not departments:
        await message.answer("В организации оборудования нет подразделений. Создайте его в приложении.")
        await state.clear()
        await back_to_main_menu(message, message.from_user.id)
        return
    await state.update_data(full_name=full_name)
    await message.answer(
        f"Сотрудник: {full_name}\nВыберите подразделение:",
        reply_markup=departments_keyboard(departments, action_prefix="newemp_dept"),
    )
    await state.set_state(NewEmployeeMoveStates.waiting_for_department)


@router.callback_query(NewEmployeeMoveStates.waiting_for_department, F.data.startswith("newemp_dept_"))
async def new_employee_move_department(callback: CallbackQuery, state: FSMContext):
    dept_id = int(callback.data.split("_")[-1])
    departments = await get_all_departments(callback.from_user.id,
                                            organization_id=(await state.get_data())["organization_id"])
    dept = next((d for d in departments if d.id == dept_id), None)
    if not dept:
        await callback.answer("Подразделение не найдено", show_alert=True)
        return
    await state.update_data(department_id=dept_id)
    data = await state.get_data()
    await callback.message.edit_text(
        "Создать сотрудника и закрепить за ним оборудование?\n\n"
        f"ФИО: {data['full_name']}\n"
        f"Организация: {dept.organization.code} {dept.organization.name}\n"
        f"Подразделение: {dept.name}",
        reply_markup=confirm_keyboard("newemp_move_yes", "cancel"),
    )
    await state.set_state(NewEmployeeMoveStates.confirmation)
    await callback.answer()


@router.callback_query(NewEmployeeMoveStates.confirmation, F.data == "newemp_move_yes")
async def new_employee_move_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    if not await can_manage_device(callback.from_user.id, data["device_id"]):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    emp = await create_employee(full_name=data["full_name"], department_id=data["department_id"], active=True,
                                admin_telegram_id=callback.from_user.id)
    if not emp:
        await callback.message.edit_text("❌ Подразделение не найдено или нет доступа.")
        await back_to_main_menu(callback, callback.from_user.id)
        return

    success, msg, movement = await change_device_responsible(data["device_id"], emp.id, callback.from_user.id)
    if success and movement:
        text, kb = movement_result(movement)
        await callback.message.edit_text(f"👤 Создан сотрудник: {emp.full_name}\n" + text, reply_markup=kb)
        await callback.answer()
    else:
        await callback.message.edit_text(f"👤 Создан сотрудник: {emp.full_name}\n❌ Перемещение: {msg}")
        await back_to_main_menu(callback, callback.from_user.id)

#
# @router.callback_query(F.data.startswith("move_print_"))
# async def print_movement_card(callback: CallbackQuery):
#     if not await is_admin(callback.from_user.id):
#         await callback.answer("⛔ Нет прав", show_alert=True)
#         return
#
#     card_id = int(callback.data.split("_")[-1])
#     success, msg = await send_movement_card_to_print(card_id, callback.from_user.id)
#     safe_msg = (msg or '')[:180]
#     await callback.answer(safe_msg, show_alert=not success)
#     if len(msg or '') > 180:
#         await callback.message.answer((msg or '')[:3500])
