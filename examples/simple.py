"""
простой пример использования парсера rutracker.org
"""

import sys
sys.path.append('..')

from rutracker_parser import rutracker_parser

from pprint import pprint

# настройка
parser = rutracker_parser(
		# ваш логин на rutracker
		username='YOUR LOGIN',
		# ваш пароль на rutracker
		password='YOUR PASSWORD',

		# ключ для работы с API разгадывания каптчей (используется antigate.com) - не обязательно
		captcha_solve_api_key='ANTIGATE API KEY',
	)

"""
получаем список форумов
метод возвращает 3х уровневую структуру: категории -> корневые форумы -> подфорумы
таким образом можно легко получить все названия и ID форумов трекера
"""
result = parser.request('forums_list')
pprint(result, indent=1)

"""
по ID форума получаем список топиков и номер последней страницы в пегинации (чтоб понимать когда остановиться)
"""
# result = parser.request('topics_list', forum_id=2093, page=191)
# pprint(result, indent=1)

"""
по ID топика получаем информацию о нем

в итоге получаем dict с такими данными:
title - название топика
main_post_body - HTML код первого поста
torrent_hash - хеш торрента (по нему можно сформулировать magnet ссылку и скачать торрент)
torrent_download_url - ссылка на скачивание torrent файла
"""
# result = parser.request('topic', topic_id=5117006)
# pprint(result, indent=1)