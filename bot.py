import asyncio
import logging
import sys
import os
from datetime import datetime
from openpyxl import Workbook

from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.exceptions import TelegramUnauthorizedError

import database as db

# Siz bergan yangi to'g'ri token:
TOKEN = "8435358260:AAEyA-gsQPjPbnW0WLdghrk8Zk9R7MOlReg"

try:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
except Exception as e:
    print(f"\n[XATO] Token formati noto'g'ri: {e}\n")
    sys.exit()

dp = Dispatcher()

# --- Admin Filter ---
class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        admin = db.db_fetchone("SELECT telegram_id FROM admins WHERE telegram_id = ?", (message.from_user.id,))
        return admin is not None

# --- States (Holatlar) ---
class RegistrationStates(StatesGroup):
    fullname = State()
    mahalla = State()
    birth_year = State()
    phone = State()
    sport = State()

class AdminStates(StatesGroup):
    add_sport_name = State()
    add_sport_limit = State()
    add_sport_min_age = State()
    add_sport_max_age = State()
    delete_sport = State()
    add_admin = State()
    broadcast = State()
    toggle_sport_status = State()

# --- Keyboards (Tugmalar) ---
def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📝 Ro'yxatdan o'tish")]], resize_keyboard=True)

def get_admin_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Sport turi qo'shish"), KeyboardButton(text="❌ Sport turini o'chirish")],
        [KeyboardButton(text="🔓 Ochish / 🔒 Yopish"), KeyboardButton(text="📋 Ishtirokchilar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📁 Excel yuklab olish")],
        [KeyboardButton(text="📢 Hammaga xabar yuborish"), KeyboardButton(text="👤 Admin qo'shish")]
    ], resize_keyboard=True)

# --- Foydalanuvchi Qismi ---
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    is_admin = db.db_fetchone("SELECT telegram_id FROM admins WHERE telegram_id = ?", (message.from_user.id,))
    if is_admin:
        await message.answer("👨‍💼 Admin panelga xush kelibsiz!", reply_markup=get_admin_menu())
    else:
        await message.answer("Salom! Mahalla sport musobaqasi botiga xush kelibsiz.", reply_markup=get_main_menu())

@dp.message(F.text == "📝 Ro'yxatdan o'tish")
async def start_reg(message: Message, state: FSMContext):
    active_sports = db.db_fetchall("SELECT name FROM sports WHERE is_active = 1")
    if not active_sports:
        await message.answer("Hozirda faol musobaqalar mavjud emas yoki ro'yxatdan o'tish yopiq.")
        return
    await message.answer("Ism va familiyangizni kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegistrationStates.fullname)

@dp.message(RegistrationStates.fullname)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await message.answer("Mahallangiz nomini kiriting:")
    await state.set_state(RegistrationStates.mahalla)

@dp.message(RegistrationStates.mahalla)
async def process_mahalla(message: Message, state: FSMContext):
    await state.update_data(mahalla=message.text)
    await message.answer("Tug'ilgan yilingizni kiriting (Masalan: 2005):")
    await state.set_state(RegistrationStates.birth_year)

@dp.message(RegistrationStates.birth_year)
async def process_year(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam kiriting:")
        return
    
    year = int(message.text)
    current_year = datetime.now().year
    age = current_year - year
    
    await state.update_data(birth_year=year, age=age)
    
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="O'tkazib yuborish")]], resize_keyboard=True)
    await message.answer("Telefon raqamingizni kiriting (ixtiyoriy, yoki tugmani bosing):", reply_markup=kb)
    await state.set_state(RegistrationStates.phone)

@dp.message(RegistrationStates.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = "Kiritilmagan" if message.text == "O'tkazib yuborish" else message.text
    await state.update_data(phone=phone)
    
    sports = db.db_fetchall("SELECT name, max_limit, min_age, max_age FROM sports WHERE is_active = 1")
    data = await state.get_data()
    user_age = data['age']
    
    valid_sports = []
    kb_list = []
    
    for s in sports:
        count = db.db_fetchone("SELECT COUNT(*) FROM participants WHERE sport_name = ?", (s[0],))[0]
        if count < s[1] and s[2] <= user_age <= s[3]:
            valid_sports.append(s[0])
            kb_list.append([KeyboardButton(text=s[0])])
            
    if not valid_sports:
        await message.answer("Kechirasiz, sizning yoshingizga mos yoki bo'sh joyi bor sport turi topilmadi.", reply_markup=get_main_menu())
        await state.clear()
        return

    kb = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True)
    await message.answer("Sport turini tanlang:", reply_markup=kb)
    await state.set_state(RegistrationStates.sport)

@dp.message(RegistrationStates.sport)
async def process_sport(message: Message, state: FSMContext):
    sport_name = message.text
    sport_info = db.db_fetchone("SELECT max_limit, min_age, max_age FROM sports WHERE name = ? AND is_active = 1", (sport_name,))
    
    if not sport_info:
        await message.answer("Noto'g'ri sport turi tanlandi. Qayta urinib ko'ring.")
        return
        
    data = await state.get_data()
    count = db.db_fetchone("SELECT COUNT(*) FROM participants WHERE sport_name = ?", (sport_name,))[0]
    if count >= sport_info[0]:
        await message.answer("Ushbu sport turiga limit to'lgan.", reply_markup=get_main_menu())
        await state.clear()
        return

    sana = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    db.db_execute("""
        INSERT INTO participants (telegram_id, fullname, mahalla, birth_year, phone, sport_name, reg_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (message.from_user.id, data['fullname'], data['mahalla'], data['birth_year'], data['phone'], sport_name, sana))
    
    await message.answer(f"✅ Siz muvaffaqiyatli ro'yxatdan o'tdingiz.", reply_markup=get_main_menu())
    
    # Adminlarga ogohlantirish yuborish
    admins = db.db_fetchall("SELECT telegram_id FROM admins")
    admin_msg = f"🏆 Yangi ishtirokchi\n\n👤 Ism: {data['fullname']}\n🏘 Mahalla: {data['mahalla']}\n🎂 Tug'ilgan yili: {data['birth_year']}\n📞 Telefon: {data['phone']}\n🥇 Sport turi: {sport_name}\n🕒 Sana: {sana}"
    
    for admin in admins:
        try:
            await bot.send_message(chat_id=admin[0], text=admin_msg)
        except Exception:
            pass
            
    await state.clear()

# --- Admin Qismi ---
@dp.message(IsAdmin(), F.text == "➕ Sport turi qo'shish")
async def admin_add_sport(message: Message, state: FSMContext):
    await message.answer("Yangi sport turi nomini kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.add_sport_name)

@dp.message(AdminStates.add_sport_name)
async def admin_sport_name(message: Message, state: FSMContext):
    await state.update_data(s_name=message.text)
    await message.answer("Maksimal ishtirokchilar limitini kiriting (Masalan: 32):")
    await state.set_state(AdminStates.add_sport_limit)

@dp.message(AdminStates.add_sport_limit)
async def admin_sport_limit(message: Message, state: FSMContext):
    await state.update_data(s_limit=int(message.text))
    await message.answer("Eng kichik yosh chegarasini kiriting (Masalan: 18):")
    await state.set_state(AdminStates.add_sport_min_age)

@dp.message(AdminStates.add_sport_min_age)
async def admin_sport_min(message: Message, state: FSMContext):
    await state.update_data(s_min=int(message.text))
    await message.answer("Eng katta yosh chegarasini kiriting (Masalan: 30):")
    await state.set_state(AdminStates.add_sport_max_age)

@dp.message(AdminStates.add_sport_max_age)
async def admin_sport_max(message: Message, state: FSMContext):
    data = await state.get_data()
    max_age = int(message.text)
    
    try:
        db.db_execute("INSERT INTO sports (name, max_limit, min_age, max_age) VALUES (?, ?, ?, ?)", 
                      (data['s_name'], data['s_limit'], data['s_min'], max_age))
        await message.answer(f"✅ Sport turi qo'shildi: {data['s_name']}", reply_markup=get_admin_menu())
    except Exception as e:
        await message.answer(f"Xatolik yuz berdi: {e}", reply_markup=get_admin_menu())
    await state.clear()

@dp.message(IsAdmin(), F.text == "❌ Sport turini o'chirish")
async def admin_del_sport_menu(message: Message, state: FSMContext):
    sports = db.db_fetchall("SELECT name FROM sports")
    if not sports:
        await message.answer("Hech qanday sport turi mavjud emas.")
        return
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=s[0])] for s in sports], resize_keyboard=True)
    await message.answer("O'chirmoqchi bo'lgan sport turingizni tanlang:", reply_markup=kb)
    await state.set_state(AdminStates.delete_sport)

@dp.message(AdminStates.delete_sport)
async def admin_delete_sport(message: Message, state: FSMContext):
    db.db_execute("DELETE FROM sports WHERE name = ?", (message.text,))
    await message.answer(f"❌ '{message.text}' muvaffaqiyatli o'chirildi.", reply_markup=get_admin_menu())
    await state.clear()

@dp.message(IsAdmin(), F.text == "🔓 Ochish / 🔒 Yopish")
async def admin_toggle_menu(message: Message, state: FSMContext):
    sports = db.db_fetchall("SELECT name, is_active FROM sports")
    if not sports:
        await message.answer("Hech qanday sport turi yo'q.")
        return
    text = "Hozirgi holat:\n"
    kb_list = []
    for s in sports:
        status = "Faol 🔓" if s[1] == 1 else "Yopiq 🔒"
        text += f"• {s[0]} - {status}\n"
        kb_list.append([KeyboardButton(text=s[0])])
    
    kb = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True)
    await message.answer(f"{text}\nHolatini o'zgartirmoqchi bo'lgan sport turini bosing:", reply_markup=kb)
    await state.set_state(AdminStates.toggle_sport_status)

@dp.message(AdminStates.toggle_sport_status)
async def admin_toggle_sport(message: Message, state: FSMContext):
    sport = db.db_fetchone("SELECT is_active FROM sports WHERE name = ?", (message.text,))
    if sport:
        new_status = 0 if sport[0] == 1 else 1
        db.db_execute("UPDATE sports SET is_active = ? WHERE name = ?", (new_status, message.text))
        status_text = "ochildi 🔓" if new_status == 1 else "yopildi 🔒"
        await message.answer(f"✅ {message.text} musobaqasi {status_text}.", reply_markup=get_admin_menu())
    else:
        await message.answer("Sport turi topilmadi.", reply_markup=get_admin_menu())
    await state.clear()

@dp.message(IsAdmin(), F.text == "📊 Statistika")
async def admin_stats(message: Message):
    sports = db.db_fetchall("SELECT name FROM sports")
    text = "📊 <b>Statistika:</b>\n\n"
    total = 0
    for s in sports:
        count = db.db_fetchone("SELECT COUNT(*) FROM participants WHERE sport_name = ?", (s[0],))[0]
        text += f"• {s[0]} - {count} ta\n"
        total += count
    text += f"\n<b>Jami: {total} ta</b>"
    await message.answer(text)

@dp.message(IsAdmin(), F.text == "📋 Ishtirokchilar")
async def admin_list(message: Message):
    parts = db.db_fetchall("SELECT fullname, mahalla, sport_name FROM participants ORDER BY id DESC LIMIT 50")
    if not parts:
        await message.answer("Hozircha ro'yxatdan o'tganlar yo'q.")
        return
    text = "📋 <b>Oxirgi 50 ta ro'yxatdan o'tganlar:</b>\n\n"
    for p in parts:
        text += f"👤 {p[0]} | 🏘 {p[1]} | 🥇 {p[2]}\n"
    await message.answer(text)

@dp.message(IsAdmin(), F.text == "📁 Excel yuklab olish")
async def admin_excel(message: Message):
    parts = db.db_fetchall("SELECT id, fullname, mahalla, birth_year, phone, sport_name, reg_date FROM participants")
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Sportchilar"
    
    ws.append(["ID", "Ism Familiya", "Mahalla", "Tug'ilgan yili", "Telefon", "Sport turi", "Sana"])
    
    for p in parts:
        ws.append(p)
        
    filename = "sportchilar.xlsx"
    wb.save(filename)
    
    from aiogram.types import FSInputFile
    document = FSInputFile(filename)
    await message.answer_document(document, caption="Barcha ro'yxatdan o'tgan sportchilar jadvali.")
    os.remove(filename)

@dp.message(IsAdmin(), F.text == "📢 Hammaga xabar yuborish")
async def admin_broadcast_prompt(message: Message, state: FSMContext):
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.broadcast)

@dp.message(AdminStates.broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    users = db.db_fetchall("SELECT DISTINCT telegram_id FROM participants")
    count = 0
    for u in users:
        try:
            await bot.send_message(chat_id=u[0], text=message.text)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"📢 Xabar {count} ta foydalanuvchiga muvaffaqiyatli yuborildi.", reply_markup=get_admin_menu())
    await state.clear()

@dp.message(IsAdmin(), F.text == "👤 Admin qo'shish")
async def admin_add_prompt(message: Message, state: FSMContext):
    await message.answer("Yangi adminning Telegram ID raqamini kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.add_admin)

@dp.message(AdminStates.add_admin)
async def admin_add_save(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID faqat raqamlardan iborat bo'lishi lozim.")
        return
    db.db_execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (int(message.text),))
    await message.answer(f"👤 Yangi admin (ID: {message.text}) muvaffaqiyatli qo'shildi.", reply_markup=get_admin_menu())
    await state.clear()

# --- Ishga Tushirish ---
async def main() -> None:
    db.init_db()
    try:
        await dp.start_polling(bot)
    except TelegramUnauthorizedError:
        print("\n[XATO] Telegram Token noto'g'ri kiritilgan! Iltimos, bot.py faylidagi tokenni tekshiring.\n")
    except Exception as e:
        print(f"\n[XATO] Kutilmagan xatolik: {e}\n")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())