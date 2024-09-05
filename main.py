import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram import F
import google.generativeai as gemini
import os
import tempfile

API_TOKEN = ""
GEMINI_API_KEY = ""


bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

gemini.configure(api_key=GEMINI_API_KEY)

class PDFStates(StatesGroup):
    waiting_for_pdf = State()
    pdf_uploaded = State()

async def upload_pdf_to_gemini(file_bytes: bytes, file_name: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(file_bytes)
        tmp_file_path = tmp_file.name

    sample_file = gemini.upload_file(path=tmp_file_path, display_name=file_name)
    file = gemini.get_file(name=sample_file.name)
    print(f"Retrieved file '{file.display_name}' as: {sample_file.uri}")

    os.remove(tmp_file_path)

    return sample_file


async def summarize_pdf_with_gemini(sample_file) -> str:
    model = gemini.GenerativeModel(model_name="gemini-1.5-flash")
    response = model.generate_content([sample_file, "Выполни суммаризацию этого документа. Выдели ключевые моменты по пунктам."])
    return response.text


async def ask_gemini_about_pdf(sample_file, question: str) -> str:
    model = gemini.GenerativeModel(model_name="gemini-1.5-flash")
    response = model.generate_content([sample_file, question])
    return response.text


@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await message.answer(
        "Отправь мне PDF документ, и я суммаризирую его, а после смогу ответить на твои вопросы о нем.")
    await state.set_state(PDFStates.waiting_for_pdf)


@dp.message(F.document.mime_type == 'application/pdf')
async def handle_pdf_document(message: types.Message, state: FSMContext):
    document = message.document

    file = await bot.download(document)
    file_bytes = file.read()

    sample_file = await upload_pdf_to_gemini(file_bytes, document.file_name)
    await state.update_data(sample_file=sample_file)

    summary = await summarize_pdf_with_gemini(sample_file)

    await message.answer(summary)
    await message.answer("Теперь вы можете спросить у меня что-нибудь о документе.")

    await state.set_state(PDFStates.pdf_uploaded)


@dp.message(F.text)
async def handle_questions(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sample_file = data.get('sample_file')

    if not sample_file:
        await message.answer("Пожалуйста отправьте PDF документ.")
        return

    question = message.text
    answer = await ask_gemini_about_pdf(sample_file, question)
    await message.answer(answer)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
