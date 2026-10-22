from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from .start import send_device_card
from ..utils.db import get_device_by_code_or_id
# from .admin_create import CreateDeviceStates

router = Router()

@router.message(F.text)
async def handle_qr_code(message: Message, state: FSMContext):
    code = message.text.strip()
    device = await get_device_by_code_or_id(code, message.from_user.id)
    await send_device_card(message, device)
    # else:
    #     admin = await is_admin(message.from_user.id)
    #     if admin:
    #         await message.answer(
    #             f"❌ Код {code} не найден в базе.\n"
    #             f"Хотите создать новую технику с этим кодом?",
    #             reply_markup=confirm_keyboard("create_device_yes", "create_device_no")
    #         )
    #         await state.set_state(CreateDeviceStates.waiting_for_confirmation)
    #         await state.update_data(qr_code=code)
    #     else:
    #         await message.answer("❌ Неверный QR-код или он деактивирован.")


# @router.callback_query(F.data == "create_device_yes")
# async def confirm_create_device(callback: CallbackQuery, state: FSMContext):
#     await callback.answer()
#     await callback.message.edit_text(
#         "Создание новой техники.\n"
#         "Введите ФИО сотрудника, за которым будет закреплена техника:"
#     )
#     await state.set_state(CreateDeviceStates.waiting_for_employee_name)


# @router.callback_query(F.data == "create_device_no")
# async def cancel_create_device(callback: CallbackQuery, state: FSMContext):
#     await callback.answer()
#     await callback.message.edit_text("Создание отменено.")
#     await state.clear()