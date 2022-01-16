from http import HTTPStatus
import json
import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
import telegram

import exceptions

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


class TelegramHandler(logging.Handler):
    """Handler для отправки логов в телеграм."""

    def __init__(self):
        """Конструктор."""
        super().__init__()
        self.chat_id = TELEGRAM_CHAT_ID
        self.last_msg = None
        self.is_recursion = False

    def emit(self, record):
        """Создание записи в логе."""
        if (self.is_recursion or self.last_msg == record.getMessage()
           or not TELEGRAM_TOKEN):
            return
        self.is_recursion = True
        send_message(telegram.Bot(token=TELEGRAM_TOKEN), self.format(record))
        self.is_recursion = False
        self.last_msg = record.getMessage()


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler_s = logging.StreamHandler(sys.stdout)
handler_t = TelegramHandler()
handler_s.setLevel(logging.DEBUG)
handler_t.setLevel(logging.ERROR)
format = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler_s.setFormatter(format)
handler_t.setFormatter(format)
logger.addHandler(handler_s)
logger.addHandler(handler_t)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Бот отправил сообщение "{message}"')
    except telegram.TelegramError as e:
        logger.error(f'Ошибка при отправке сообщения в telegram: {e}')


def get_api_answer(current_timestamp):
    """Делает запрос к API Практикум.Домашка."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise exceptions.HTTPError(
                'HTTP-запрос вернул неверный код состояния: '
                f'{response.status_code}')
        return response.json()
    except requests.RequestException:
        raise requests.RequestException(
            'Сетевая ошибка при подключении к серверу домашки')
    except json.decoder.JSONDecodeError:
        raise exceptions.JSONDecodeError('Ошибка декодирования JSON')
    except exceptions.HTTPError:
        raise
    except Exception as e:
        raise Exception(f'Другая ошибка при запросе к API: {e}')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if ('homeworks' in response
       and isinstance(response['homeworks'], list)):
        return response['homeworks']
    raise exceptions.APIFormatError(
        'Не верный формат ответа API для всех работ')


def parse_status(homework):
    """Извлекает статус работы из информации о конкретной домашней работе."""
    if 'homework_name' not in homework or 'status' not in homework:
        raise exceptions.APIFormatError(
            'Не верный формат ответа API для конкретной работы')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise exceptions.StatusError(
            f'Недокументированный статус домашней работы: "{homework_status}"')
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
        raise exceptions.EnvVarsError(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
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
        except Exception as e:
            logger.error(f'Сбой в работе программы: {e}')
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
