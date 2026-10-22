from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from ..utils.db import (
    get_user_by_telegram,
    get_device_by_code_or_id,
    can_manage_device,
    is_admin
)
from ..keyboards.inline import main_menu_keyboard, device_actions_keyboard

router = Router()

def get_status_text(status_code):
    status_map = {
        'in_use': '✅ используется',
        'reserve': '🔸 резерв',
        'repair': '🛠 в ремонте',
        'to_transfer' : '🔁 на передачу',
        'to_write_off': '🙅 на списание',
        'written_off' : '❌ списан',
    }
    return status_map.get(status_code, '❓ Неизвестно')

def device_card_text(device):
    return (
        f"🔹 <b>{device.name}</b>\n"
        f"📌 Инв. номер: {device.inventory_number or '—'}\n"
        f"🏷 Тип: {device.equipment_type.name}\n"
        f"🏢 Организация: {device.organization.code} {device.organization.name}\n"
        f"👤 Ответственный: {device.assigned_to.full_name if device.assigned_to else '—'}\n"
        f"⚙️ Статус: {get_status_text(device.status)}\n"
        f"🔢 Серийный №: {device.serial_number or '—'}"
    )


async def send_device_card(message: Message, device):
    """Карточка оборудования после сканирования QR + меню действий."""
    if not device:
        await message.answer("❌ Устройство с таким кодом не найдено.",
                             reply_markup=device_actions_keyboard(0, can_manage=False))
        return
    can_manage = await can_manage_device(message.from_user.id, device.id)
    await message.answer(
        device_card_text(device) + ("\n\nЧто сделать с оборудованием?" if can_manage else ""),
        reply_markup=device_actions_keyboard(device.id, can_manage),
    )


@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    args = command.args
    if args:
        # Если пришли с параметром (из QR-кода)
        device = await get_device_by_code_or_id(args, message.from_user.id)
        await send_device_card(message, device)
        return

    # Обычный /start без параметра
    telegram_id = message.from_user.id
    user = await get_user_by_telegram(telegram_id)
    if user and user.is_active:
        await message.answer(
            f"👋 Здравствуйте, {user.get_full_name()}!",
            reply_markup=main_menu_keyboard(True)
        )
    else:
        await message.answer(
            f"👋 Добро пожаловать!\n\n"
            "Этот бот предназначен для инвентаризации оборудования.\n"
            "Вы можете сканировать QR-коды, наклеенные на технику, и получать информацию о ней.\n\n"
            "Просто отправьте код с QR-кода (или перейдите по ссылке) – и бот покажет данные об устройстве.",
            reply_markup=main_menu_keyboard(False)
        )

@router.callback_query(F.data == "qr_info")
async def callback_qr_info(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        f"📌 Для получения информации о технике просто отсканируйте QR-код камерой телефона.\n"
        "После сканирования откроется диалог с ботом, и вы увидите данные об устройстве.\n"
        "Если техника закреплена за вами, вы увидите подробные данные, иначе – общую информацию."
    )