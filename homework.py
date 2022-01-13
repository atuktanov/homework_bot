import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
import telegram

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
format = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(format)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.info(f'Бот отправил сообщение "{message}"')


def get_api_answer(current_timestamp):
    """Делает запрос к API Практикум.Домашка."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != requests.codes.ok:
        raise requests.exceptions.HTTPError(f'Код {response.status_code}')
    # Такой вариант не проходит pytest
    # response.raise_for_status()
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    return response['homeworks'][::]


def parse_status(homework):
    """Извлекает статус работы из информации о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Не установлены переменные окружения'
        logger.critical(message)
        raise NameError(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    old_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                logger.debug('В ответе отсутствуют новые статусы')
            for homework in homeworks:
                status = parse_status(homework)
                send_message(bot, status)
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = ('Сбой в работе программы. '
                       f'Тип: {error.__class__}, ошибка: {error}')
            logger.error(message)
            if old_message != message:
                old_message = message
                try:
                    send_message(bot, message)
                except Exception:
                    pass
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
