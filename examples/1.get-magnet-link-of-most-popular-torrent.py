# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

sys.path.append("../")
from config import *
from rutracker_parser import *

# Пример использования

# инициализация, указываем логин и пароль от трекера rutracker.org
bot=rutrackerBot({
	"username":RUTRACKER_USER,
	"password":RUTRACKER_PASSWORD
});

# получаем список топиков из первой страницы форума "Фильмы 1991-2000" (id: 2221)
topics=bot.get_forum_topics(2221,1)

# из этого списка получаем самый популярный по раздаче топик
topics=sorted(topics,key=lambda x: x['seeders'],reverse=True)

# получаем подробную информацию об этом топике
topic_data=bot.get_topic(topics[0]['id'])

# выводим magnet ссылку для скачивания torrent'а
print topic_data['torrent_magnet_link']