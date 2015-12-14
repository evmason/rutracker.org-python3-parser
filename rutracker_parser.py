"""
rutracker.org - python3-parser

rutracker_parser - позволяет работать с популярным торрент трекером rutracker.org из Python3
"""

import re

import requests
import bs4
import collections

import http.cookiejar
from urllib.parse import urlparse, parse_qs

import base64
import time

import logging
#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: [%(levelname)s] %(message)s', datefmt='%m/%d/%Y %H:%M:%S')

class rutracker_parser():
	# путь к файлу cookies
	cookie_file_path = 'rutracker.cookie.txt'

	# логин для входа
	username = ''

	# паролья для входа
	password = ''

	# сервис для работы с каптчей
	# можно использовать альтернативные сервисы заменив URL, API у них идентичны
	captcha_solve_config = {
		'api_url_put': 'http://antigate.com/in.php',
		'api_url_result': 'http://antigate.com/res.php',
		'key': ''
	}

	# основные HTTP заголовки
	headers = {
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
		'Connection': 'close',
		'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4',
		'Accept-Encoding': 'gzip, deflate, lzma, sdch',
		'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
	}

	def __init__(self, **params):
		if 'username' in params:
			self.username = params['username']

		if 'password' in params:
			self.password = params['password']

		if 'captcha_solve_api_key' in params:
			self.captcha_solve_config['key'] = params['captcha_solve_api_key']

		self.session = requests.Session()

	# чтение cookies
	def cookie_read(self):
		self.session.cookies = http.cookiejar.LWPCookieJar(self.cookie_file_path)
		try:
			self.session.cookies.load(ignore_discard=True)
		except:
			pass

	# запись cookies
	def cookie_write(self):
		self.session.cookies.save(ignore_discard=True)

	# пытаемся разгадать каптчу
	def solve_captcha(self, html):
		result = {}

		match = re.search('<input[^>]*name="cap_sid"[^>]*value="([^"]+)"[^>]*>', html)
		if match is not None:
			result['cap_sid'] = match.group(1)
		else:
			return False

		match = re.search('<input[^>]*name="(cap_code_[^"]+)"[^>]*value="[^"]*"[^>]*>', html)
		if match is not None:
			result['cap_code_name'] = match.group(1)
		else:
			return False

		match = re.search('<img[^>]*src="([^"]+/captcha/[^"]+)"[^>]*>', html)
		if match is not None:
			captcha_img_url = match.group(1)
		else:
			return False

		# скачиваем изображение каптчи
		response = requests.get(
			captcha_img_url, 
			timeout=60, 
			stream=True, 
			verify=False, 
			headers=self.headers
		)
		if response.status_code != 200:
			return False
		captcha_img_data = response.raw.read()

		post_data = {
			'method': 'base64',
			'key': self.captcha_solve_config['key'],
			'phrase': 0,
			'regsense': 0,
			'numeric': 0,
			'min_len': 0,
			'max_len': 0,
			'body': base64.b64encode(captcha_img_data),
		}

		# отправляем каптчу в сервис распознавания
		response = requests.post(
			self.captcha_solve_config['api_url_put'],
			data=post_data,
			timeout=60,
			stream=True,
			verify=False,
			headers=self.headers
		)

		if response.status_code != 200 or 'OK|' not in response.text:
			return False

		status, service_captcha_id = response.text.split('|')
	
		# стучимся в сервис пока не получим содержимое каптчи
		i = 0
		while True:
			# 5мин. не можем разгадать каптчу
			# пора бы остановиться...
			if i == 300:
				break

			logging.debug('Try to get captcha solve result...')

			response = requests.get(
				'%s?key=%s&id=%s&action=get' % (self.captcha_solve_config['api_url_result'], self.captcha_solve_config['key'], service_captcha_id),
				timeout=60, 
				stream=True, 
				verify=False, 
				headers=self.headers
			)
			
			if 'OK|' in response.text:
				status, result['captcha_code'] = response.text.split('|')
				
				return result

			time.sleep(1)

			i += 1

		return False

	# по содержимому страницу определяет залогинен пользователь или нет
	def is_login_check(self, html):
		return 'logged-in-as-cap' in html

	# логинимся
	def login(self, captcha_info=None):
		params = {}

		if captcha_info is not None:
			params['captcha_info'] = captcha_info

		return self.request('login', **params)

	# отправляем запрос на rutracker
	def request(self, method_name, **request_params):
		# читаем куки
		self.cookie_read()

		shema = 'get'
		if method_name == 'forums_list':
			url = 'http://rutracker.org/forum/index.php'
		elif method_name == 'login':
			shema = 'post'
			url = 'http://login.rutracker.org/forum/login.php'
			post_data = {
				'login_username': self.username,
				'login_password': self.password,
				'login': 'вход',
			}

			# добавляем в POST данные код каптчи
			if 'captcha_info' in request_params:
				post_data['cap_sid'] = request_params['captcha_info']['cap_sid']
				post_data[request_params['captcha_info']['cap_code_name']] = request_params['captcha_info']['captcha_code']
		elif method_name == 'topics_list':
			pagination_start = 0
			if 'page' in request_params:
				pagination_start = 50 * (int(request_params['page']) - 1)

			if 'forum_id' in request_params:
				forum_id = request_params['forum_id']
			else:
				logging.critical('Forum ID not set')
				return False

			url = 'http://rutracker.org/forum/viewforum.php?f=%s&start=%s' % (forum_id, pagination_start)
		elif method_name == 'topic':
			url = 'http://rutracker.org/forum/viewtopic.php?t=5117006'
		else:
			logging.warning('Unknown request method!')
			return False

		logging.debug('REQUEST URL: %s' % url)

		# отправляем запрос
		if shema == 'get':
			response = self.session.get(url, timeout=60, stream=True, verify=False, headers=self.headers)
		else:
			response = self.session.post(url, data=post_data, timeout=60, stream=True, verify=False, headers=self.headers)

		# преображаем контент в кодировку UTF-8
		if ('content-type' in response.headers
				and ('html' in response.headers['Content-Type']
					or 'gzip' in response.headers['Content-Type'])):
				content_raw = response.raw.read(decode_content=True)
				content_decoded = content_raw.decode('windows-1251')

		if self.is_login_check(content_decoded) is False:
			if method_name == 'login':
				logging.critical('Bad username or password!')

				if 'cap_code_' in content_decoded and self.captcha_solve_config['key'] != '':
					# это каптча! попробуем ее решить 5 раз
					for attempt in range(1, 5):
						captcha_info = self.solve_captcha(content_decoded)

						if captcha_info is not False:
							break

					if captcha_info is not False:
						# еще раз пробуем войти, но тереть с каптчей
						if self.login(captcha_info=captcha_info) is False:
							return False
					else:
						# всетаки каптчу решить не удалось
						return False
				else:
					# каптчи нет, и войти не получается.. значит другие проблемы..
					return False
			else:
				logging.debug('Try to login...')

				if self.login() is False:
					return False

				return self.request(method_name, **request_params)
		
		# записываем в cookies
		self.cookie_write()

		soup = bs4.BeautifulSoup(content_decoded, "html.parser")

		result = collections.OrderedDict()

		if method_name == 'forums_list':
			# парсим основные категории
			for category in soup.select('#forums_wrap div.category'):
				category_title = category.select('h3.cat_title a')
				category_id = category_title[0].attrs['href'].split('c=')[-1]
				
				result[category_id] = {
					'title': category_title[0].text,
					'href': category_title[0].attrs['href'],
					'childs': collections.OrderedDict(),
				}

				# парсим корневые разделы форумов
				for root_forum in category.select('table.forums tr'):
					root_forum_title = root_forum.select('h4.forumlink a')
					forum_id = self.forum_id_from_href(root_forum_title[0].attrs['href'])

					result[category_id]['childs'][forum_id] = {
						'title': root_forum_title[0].text,
						'id': self.forum_id_from_href(root_forum_title[0].attrs['href']),
						'childs': collections.OrderedDict(),
					}

					for sub_forum in root_forum.select('.subforums .sf_title a[href^=viewforum]'):
						sub_forum_id = self.forum_id_from_href(sub_forum.attrs['href'])

						result[category_id]['childs'][forum_id]['childs'][sub_forum_id] = {
							'title': sub_forum.text,
							'id': sub_forum_id,
						}

		elif method_name == 'topics_list':
			# парсим список топиков
			result['topics'] = collections.OrderedDict()
			for topic in soup.select('tr.hl-tr'):
				topic_title = topic.select('a.tt-text')

				topic_id = self.topic_id_from_href(topic_title[0].attrs['href'])
				result['topics'][topic_id] = {
					'id': topic_id,
					'title': topic_title[0].text,
				}

				topic_seedmed = topic.select('span.seedmed')
				if len(topic_seedmed) > 0:
					result['topics'][topic_id]['seedmed'] = topic_seedmed[0].text

				topic_leechmed = topic.select('span.leechmed')
				if len(topic_leechmed) > 0:
					result['topics'][topic_id]['leechmed'] = topic_leechmed[0].text

				f_dl = topic.select('div.small a.f-dl')
				if len(f_dl) > 0:
					result['topics'][topic_id]['torrent_data_size'] = f_dl[0].text
					result['topics'][topic_id]['torrent_download_url'] = f_dl[0].attrs['href']

			# парсим пегинацию
			current_page = soup.select('.bottom_info #pagination p[style*=right] b')
			
			if len(current_page) > 0:
				result['pagination'] = collections.OrderedDict()

				result['pagination']['current_page'] = int(current_page[0].text)

				for pagination_item in soup.select('.bottom_info #pagination p[style*=right] a[href^=viewforum]'):
					if str.isnumeric(pagination_item.text):
						result['pagination']['max_page'] = int(pagination_item.text)

				if result['pagination']['max_page'] < result['pagination']['current_page']:
					del(result['pagination']['max_page'])

		elif method_name == 'topic':
			topic_title = soup.select('h1.maintitle')
			result['title'] = topic_title[0].text

			topic_main_post_body = soup.select('table#topic_main .message .post_body')

			# получаем тело первого поста
			main_post_body = str(topic_main_post_body[0]).split('<div class="spacer_12"></div>')[0]
			
			# заменяем <var теги на <img
			main_post_body = re.sub('<var([^>]*)title="([^"]+)"([^>]*)>','<img\\1src="\\2"\\3>', main_post_body)
			result['main_post_body'] = main_post_body.replace('</var>', '')

			attach = topic_main_post_body[0].select('table.attach')
			if len(attach) > 0:
				torrent_hash = attach[0].select('#tor-hash')
				if len(torrent_hash) > 0:
					result['torrent_hash'] = torrent_hash[0].text

				torrent_download_url = attach[0].select('p a.dl-stub.dl-link')
				if len(torrent_download_url) > 0:
					result['torrent_download_url'] = torrent_download_url[0].attrs['href']

		return result

	# извлекает ID форума из URL на форум
	def forum_id_from_href(self, href):
		try:
			variables = parse_qs(href.split('?')[1])

			return int(variables['f'][0])
		except:
			pass

		return False

	# извлекает ID топика из URL на топик
	def topic_id_from_href(self, href):
		try:
			variables = parse_qs(href.split('?')[1])

			return int(variables['t'][0])
		except:
			pass

		return False