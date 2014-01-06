# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

"""
Copyright (c) 2014, Evgeny Mason.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import urllib, urllib2, cookielib
import pycurl
import cStringIO
import re
import lxml.html as lh
from termcolor import colored

def http_get(d,history=[]):
	buf=cStringIO.StringIO()
	headers=cStringIO.StringIO()

	url=d['url']

	c=pycurl.Curl()
	c.setopt(c.URL,url)
	c.setopt(c.WRITEFUNCTION,buf.write)
	c.setopt(c.HEADERFUNCTION,headers.write)
	c.setopt(c.CONNECTTIMEOUT,15)
	c.setopt(c.TIMEOUT,18)

	# это POST запрос
	if "postfields" in d.keys():
		c.setopt(c.POST,True)
		c.setopt(c.POSTFIELDS,d['postfields'])

	c.setopt(c.COOKIEFILE,"cookie.txt")
	c.setopt(c.COOKIEJAR,"cookie.txt")

	if "verbose" in d.keys() and d['verbose']:
		c.setopt(c.VERBOSE,True)
	else:
		d['verbose']=False

	c.setopt(pycurl.HTTPHEADER, [
		"User-Agent: 10.0.648.205 Mac OS X — Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_7; en-US) AppleWebKit/534.16 (KHTML, like Gecko) Chrome/10.0.648.205 Safari/534.16"
	])
	c.perform()

	default_charset="utf-8"
	charset="utf-8"
	m=re.search("(<meta[^>]*content *= *['\"][^'\"]*charset *= *([^=]+)['\"][^>]*>)",buf.getvalue().decode('utf8',"ignore"))
	if m:
		charset=m.group(2)
	
	if default_charset != charset:
		html=buf.getvalue().decode(charset).encode(default_charset).replace(m.group(1),'<meta http-equiv="Content-Type" content="text/html; charset='+default_charset+'" />')
	else:
		html=buf.getvalue()

	history.append({
		"http_code":c.getinfo(pycurl.HTTP_CODE),
		"headers":headers.getvalue(),
		"html":html,
		"charset":charset
	})

	d['level']=len(history)

	if(len(history)==10):
		return history
	
	redirect_uri=""

	# 300й статус ответа, значит надо делать редирект
	if(str(c.getinfo(pycurl.HTTP_CODE))[:2]=="30"):
		m=re.search('Location: *([^\n]+)',headers.getvalue())

		if not m:
			return False;

		redirect_uri=m.group(1)
	
	# проверяем, может быть есть meta тег для редиректа
	if redirect_uri == "":
		m2=re.search("<meta[^>]*http-equiv *= *['\"]Refresh['\"][^>]*URL *= *([^=>\"']+)[^>]*>",html)
		if m2:
			redirect_uri=m2.group(1).strip()

	# домебаляем в начало URL домен, если он не указан
	if(redirect_uri
		and redirect_uri[:5]!="http:" 
		and redirect_uri[:6]!="https:"):
			m=re.search('(https?://)?([^/]+)',url)
			if(m):
				main_domain=m.group(2)
				redirect_uri="http://"+main_domain+"/"+redirect_uri.lstrip("/");
	if redirect_uri:
		http_get({
			"url":redirect_uri,
			"level":d['level'],
			"verbose":d['verbose']
		},history)

	c.close()
	buf.close()
	headers.close()

	return {
		"history":history
	};

class rutrackerBot:
	debug=False
	username=""
	password=""
	index_url="http://rutracker.org/forum/index.php"

	# инициализация
	def __init__(self,d):
		if "username" in d.keys():
			self.username=d['username']

		if "password" in d.keys():
			self.password=d['password']

		if "debug" in d.keys():
			self.debug_file=open("rutracker-parser-debug.txt","a")
			self.debug=d['debug']

	def is_logged_in(self,html):
		if html != "":
			if "login_username" not in html and "login_password" not in html:
				return True

		return False

	def get_magnet_link(self,btih):
		return "magnet:?xt=urn:btih:"+btih

	def is_ready_for_download(self,status):
		if status == "проверено" or status == "checked":
			return True
		return False

	# конвертирует статус торрента на английский
	def torrent_status_translate(self,status_ru):
		status_ru=status_ru.strip()
		torrent_statuses={
			u"не проверено":"not tested",
			u"проверяется":"verified",
			u"проверено":"checked",
			u"недооформлено":"not fully decorated",
			u"не оформлено":"not decorated",
			u"повтор":"duplicate",
			u"закрыто правообладателем":"closed by rightholder",
			u"закрыто":"closed",
			u"временная":"temporal",
			u"поглощено":"absorbed",
			u"сомнительно":"doubtfully",
			u"премодерация":"premoderation"
		};

		if status_ru in torrent_statuses.keys():
			return torrent_statuses[status_ru]

		return False

	# получаем конкретный топик
	def get_topic(self,topic_id):
		response=http_get({
			"url":self.get_topic_link(topic_id)
		})

		if(response['history'][-1]['http_code'] == 200):
			if not self.is_logged_in(response['history'][-1]['html']):
				if not self.login():
					return False
				else:
					return self.get_forum_topics(forum_id,page)

			dom=lh.fromstring(response['history'][-1]['html'])

			topic_data={};

			# получаем заголовок
			h1=dom.cssselect("h1.maintitle > a")
			topic_data['title']=h1[0].text;

			if len(dom.cssselect("var.postImg[title!='']")) > 0:
				topic_data['main_picture']=dom.cssselect("var.postImg")[0].attrib['title']
			
			if len(dom.cssselect("span.seed > b"))>0:
				topic_data['seeders']=dom.cssselect("span.seed > b")[0].text

			if len(dom.cssselect("span.leech > b"))>0:
				topic_data['leechers']=dom.cssselect("span.leech > b")[0].text
			
			if len(dom.cssselect("div.post_body"))>0:
				topic_data['text']=dom.cssselect("div.post_body")[0].text_content()

			topic_data['torrent_file_link']=self.get_torrent_link(topic_id)

			if len(dom.cssselect("span#tor-hash"))>0:
				topic_data['torrent_hash']=dom.cssselect("span#tor-hash")[0].text_content()

			if topic_data['torrent_hash'] != "":
				topic_data['torrent_magnet_link']=self.get_magnet_link(topic_data['torrent_hash'])
			
			if len(dom.cssselect(".tor-icon + a"))>0:
				topic_data['torrent_status_ru']=dom.cssselect(".tor-icon + a")[0].text_content()

			if topic_data['torrent_status_ru'] != "":
				topic_data['torrent_status']=self.torrent_status_translate(topic_data['torrent_status_ru'])
			
			if topic_data['torrent_status'] != "":
				topic_data['is_ready_for_download']=self.is_ready_for_download(topic_data['torrent_status'])

			return topic_data

		return False

	# получаем список топиков по ID форума
	def get_forum_topics(self,forum_id,page=1):
		response=http_get({
			"url":self.get_forum_link(forum_id)
		})

		topics=[]
		
		if(response['history'][-1]['http_code'] == 200):
			if not self.is_logged_in(response['history'][-1]['html']):
				if not self.login():
					return False
				else:
					return self.get_forum_topics(forum_id,page)

			dom=lh.fromstring(response['history'][-1]['html'])
			for tr in dom.cssselect("tr.hl-tr"):
				a=tr.cssselect("a.torTopic")
				if len(a) != 1: continue

				seeders=0
				leechers=0
				if len(tr.cssselect("span.seedmed b")) != 1: continue
				
				seeders=tr.cssselect("span.seedmed b")[0].text.strip()
				leechers=tr.cssselect("span.leechmed b")[0].text.strip()

				topic_id=a[0].attrib['href'].split("=")[-1]
				topics.append({
					"seeders":int(seeders),
					"leechers":int(leechers),
					"id":int(topic_id),
					"title":a[0].text
				})
				
			return topics
		else:
			return False

	# получает ID форума, и возвращает кол. страниц
	def get_forum_pages_num(self,forum_id):
		response=http_get({
			"url":self.get_forum_link(forum_id)
		})

		if(response['history'][-1]['http_code'] == 200):
			dom=lh.fromstring(response['history'][-1]['html'])
			return dom.cssselect("#pagination b:last-child")[0].text.strip()
		else:
			return False

	# генерирует ссылку на торрент
	def get_torrent_link(self,topic_id):
		if topic_id == 0 or topic_id == "": return False

		return "http://dl.rutracker.org/forum/dl.php?t="+str(topic_id)

	# генерирует ссылку на топик
	def get_topic_link(self,topic_id):
		if topic_id == 0 or topic_id == "": return False

		return "http://rutracker.org/forum/viewtopic.php?t="+str(topic_id)

	# генерирует ссылку на форум
	def get_forum_link(self,forum_id):
		if forum_id == 0 or forum_id == "": return False

		return "http://rutracker.org/forum/viewforum.php?f="+str(forum_id)

	# возвращает список форумов (название, id, ссылка)
	def get_forum_structure(self):
		response=http_get({
			"url":"http://rutracker.org/forum/search.php"
		})

		if(response['history'][-1]['http_code'] == 200):
			options=[]
			dom=lh.fromstring(response['history'][-1]['html'])
			for option in dom.cssselect("select[name='f[]'] option"):

				if option.attrib['value'] == "" or option.attrib['value'] == 0: continue

				options.append({
					"value":option.attrib['value'],
					"title":option.text,
					"link":self.get_forum_link(option.attrib['value'])
				})

				return options;
		else:
			return False

	# метод отвечает за вход на rutracker
	def login(self):
		response=http_get({
			"url":self.index_url
		});

		if response['history'][-1]['http_code'] != 200:
			return False

		if type(response) is dict:
			html=response['history'][-1]['html']

			if self.debug:
				self.debug_file.write(html)

			if html.find("profile.php?mode=editprofile") > 0:
				return True
			
			rutracker_login_form_data={}
			dom=lh.fromstring(html)
			rutracker_login_form_data['form_action']=""
			for form in dom.cssselect("form"):
				if ("action" in form.attrib.keys()):
					rutracker_login_form_data['form_action']=form.attrib['action']

				if "forum/login.php" not in rutracker_login_form_data['form_action']:
					continue

				rutracker_login_form_data['fields_data']=""
				for html_input in form.cssselect("input"):

					if(html_input.attrib['name'] == "login_username"):
						html_input.attrib['value']=self.username

					if(html_input.attrib['name'] == "login_password"):
						html_input.attrib['value']=self.password

					if "name" in html_input.attrib.keys() and "value" in html_input.attrib.keys():
						rutracker_login_form_data['fields_data']+="&"+html_input.attrib['name']+"="+html_input.attrib['value'].encode("cp1251")
		
		if type(rutracker_login_form_data) is dict:
			post_response=http_get({
				"url":rutracker_login_form_data['form_action'],
				"postfields":rutracker_login_form_data['fields_data']
			})

			if self.debug:
				self.debug_file.write(post_response['history'][-1]['html'])

		return True