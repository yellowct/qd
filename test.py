from flask import Flask, render_template, request
import pymysql
import json
import requests
import random
import traceback
from lxml import etree
from requests.cookies import RequestsCookieJar
import time

app = Flask(__name__)
db = pymysql.connect('localhost', 'root', '', 'qidian')
mysql = db.cursor()


@app.route('/', methods=['GET', 'POST'])
def test():
    return 'hello world'


@app.route('/index')
def index():
    return render_template('index.html')


# 初始化页面数据
@app.route('/init', methods=['GET'])
def init():
    # 获取上次更新时间
    sql1 = "select date from novels"
    # 统计作品数量
    sql2 = "select count(*) from novels"
    # 统计各类型数量
    sql3 = "select type,count(type) as total from novels group by type"
    mysql.execute(sql1)
    data = mysql.fetchone()
    #转换为其他日期格式
    timeArray = time.localtime(data[0])
    res1 = time.strftime("%Y-%m-%d", timeArray)
    mysql.execute(sql2)
    res2 = mysql.fetchone()
    mysql.execute(sql3)
    res3 = mysql.fetchall()
    arr = []
    arr.append(res1)
    result = [e + tuple(arr) for e in res3]

    return ({
        'code': 1,
        'data1': result,
        'data2': res2[0],
        'data3': len(res3)
    })


# 爬取所有小说信息到数据库
@app.route('/get_list', methods=['GET'])
def get_list():
    delete = mysql.execute("delete from novels")
    if delete:
        res = get_info()
        return ({'code': 1, 'data': res})
    else:
        return ({'code': 0, 'data': '爬取失败'})


# @app.route('/get_all', methods=['GET', 'POST'])
# def get_all():
#     sql = "select * from novels where name like %s"
#     mysql.execute(sql, ('%临%'))
#     res = mysql.fetchall()
#     # print(res)
#     # res = json.dumps(dict(res))
#     # print(type(res))
#     return ({'code': 0, 'data': res})


def random_user_agent():
    list = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML like Gecko) Chrome/44.0.2403.155 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2226.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.4; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2225.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2225.0 Safari/537.36'
    ]
    seed = random.randint(0, len(list) - 1)
    return list[seed]


# 模拟vip请求头
def vip(url):
    headers = {
        'authority':
        'vipreader.qidian.com',
        'path':
        '/chapter/1017125042/514658310',
        'scheme':
        'https',
        'accept':
        'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'accept-encoding':
        'gzip, deflate, br',
        'accept-language':
        'zh-CN,zh;q=0.9',
        'cache-control':
        'max-age=0',
        'cookie':
        '_yep_uuid=87320c31-0021-da3b-3cb3-f933c7992fe0; '
        'e1=%7B%22pid%22%3A%22qd_P_vipread%22%2C%22eid%22%3A%22%22%7D; '
        'e2=%7B%22pid%22%3A%22qd_P_vipread%22%2C%22eid%22%3A%22%22%7D; _'
        'csrfToken=3xUPYN0oA11algWeniisyWNVgS1qvpyAkcI5ghOp; '
        'newstatisticUUID=1599708891_1656017197; '
        'qdrs=0%7C3%7C0%7C0%7C1; '
        'showSectionCommentGuide=1; '
        'qdgd=1; rcr=1017125042; '
        'ywguid=3312479960; '
        'ywkey=ywWkCIc4XCB4; '
        'ywopenid=051DB7D637B40C9DE4EE0CA86998CE54; '
        'lrbc=1017125042%7C514658310%7C1; '
        'pageOps=1; '
        'bc=1017125042',
        'referer':
        'https://book.qidian.com/info/1017125042',
        'sec-fetch-dest':
        'document',
        'sec-fetch-mode':
        'navigate',
        'sec-fetch-site':
        'none',
        'sec-fetch-user':
        '?1',
        'upgrade-insecure-requests':
        '1',
        'user-agent':
        random_user_agent()
    }
    s = requests.session()
    c = RequestsCookieJar()

    c.set("ptui_loginuin", "3312479960", path='/', domain='.qq.com')
    c.set("0.6491143821462142", "0_5f0e5abcdff73", path='/', domain='.qq.com')
    c.set("iip", "0", path='/', domain='.qq.com')
    c.set("pgv_pvid", "595269072", path='/', domain='.qq.com')
    c.set("pgv_pvi", "1196980224", path='/', domain='.qq.com')
    c.set("lrbc", "1017125042%7C514658310%7C1", path='/', domain='.qidian.com')
    c.set("bc", "1017125042", path='/', domain='.qidian.com')
    c.set("pageOps", "1", path='/', domain='.vipreader.qidian.com')
    c.set("RK", "4lJBB1PDbJ", path='/', domain='.qq.com')
    c.set("ywopenid",
          "051DB7D637B40C9DE4EE0CA86998CE54",
          path='/',
          domain='.qidian.com')
    c.set("ptcz",
          "68122e8d03b749e241db8d81e3731925f935e7c305943fde9ab0d5b44225341c",
          path='/',
          domain='.qq.com')
    c.set("newstatisticUUID",
          "1599708891_1656017197",
          path='/',
          domain='.qidian.com')
    c.set("ywkey", "ywWkCIc4XCB4", path='/', domain='.qidian.com')
    c.set("qdrs", "0%7C3%7C0%7C0%7C1", path='/', domain='.qidian.com')
    c.set("rcr", "1017125042", path='/', domain='.qidian.com')
    c.set("ywguid", "3312479960", path='/', domain='.qidian.com')
    c.set("qdgd", "1", path='/', domain='.qidian.com')
    c.set("ywguid", "3312479960", path='/', domain='.qidian.com')
    c.set("_qpsvr_localtk", "0.6491143821462142", path='/', domain='.qq.com')
    c.set("showSectionCommentGuide", "1", path='/', domain='.qidian.com')
    c.set("pgv_si", "s4360745984", path='/', domain='.qq.com')
    c.set("e2",
          "%7B%22pid%22%3A%22qd_P_vipread%22%2C%22eid%22%3A%22%22%7D",
          path='/chapter/1017125042',
          domain='.qidian.com')
    c.set("_csrfToken",
          "3xUPYN0oA11algWeniisyWNVgS1qvpyAkcI5ghOp",
          path='/',
          domain='.qidian.com')
    c.set("e1",
          "%7B%22pid%22%3A%22qd_P_vipread%22%2C%22eid%22%3A%22%22%7D",
          path='/chapter/1017125042',
          domain='.qidian.com')
    c.set("_yep_uuid",
          "87320c31-0021-da3b-3cb3-f933c7992fe0",
          path='/chapter/1017125042',
          domain='vipreader.qidian.com')
    s.cookies.update(c)
    return s.get(url, headers=headers, timeout=3).text


# 爬取过程
def spider(url, headers):
    count = 0
    # print(count)
    while True:
        if count < 5:
            try:
                if url[7:10] == 'vip':
                    res = vip(url)
                else:
                    res = requests.get(url, headers=headers, timeout=5).text
                # print(res)
                return res
            except Exception:
                print('请求超时，第%s次重复请求' % count)
                time.sleep(3)
                traceback.print_exc()
                count += 1
                continue
        else:
            print('爬取失败')
            break


# 爬取小说内容
def run(book_id):
    headers = {'User-Agent': random_user_agent()}
    url = "https://book.qidian.com/info/" + book_id
    html = requests.get(url, headers=headers).text
    html = etree.HTML(html)
    name = html.xpath('//div[@class="book-info "]/h1/em/text()')  #爬取书名
    Lit_tit_list = html.xpath('//ul[@class="cf"]/li/a/text()')  #爬取每个章节名字
    Lit_href_list = html.xpath('//ul[@class="cf"]/li/a/@href')  #每个章节链接
    # print(Lit_tit_list)
    # print(Lit_href_list)
    stop = 1
    for tit, src in zip(Lit_tit_list, Lit_href_list):
        url = "http:" + src
        res = spider(url, headers)
        html = etree.HTML(res)
        text_list = html.xpath(
            '//div[@class="read-content j_readContent"]/p/text()')
        text = "".join(text_list).replace('　　', '')
        print(text)
        exit()
        # file_name = tit + ".txt"
        print("正在抓取文章：" + tit)
        # db['novels'].insert_one({'name': name[0], 'chapter': tit})
        # db['chapters'].insert_one({'name': tit, 'content': text})
        sql = "insert IGNORE into chapters (novel,chapter,content) values (%s,%s,%s)"
        mysql.execute(sql, (name[0], tit, text))
        db.commit()
        # with open(r'D:\Python\book//' + file_name, 'a', encoding="utf-8") as f:
        #     f.write("\t" + tit + '\n' + text)
        if stop % 50 == 0:
            time.sleep(2)
            print('休息2秒')
        stop += 1


# 爬取各类型小说的信息
def get_info():
    res1 = getType('man')
    res2 = getType('woman')
    if res1 == 'succ' and res2 == 'succ':
        return '爬取成功'
    else:
        return '爬取失败'


def getType(sex):
    headers = {'User-Agent': random_user_agent()}
    if sex == 'man':
        url = 'https://www.qidian.com/all?orderId=&style=1&pageSize=20&siteid=1&pubflag=0&hiddenField=0'
    else:
        url = 'https://www.qidian.com/mm/all?orderId=&style=1&pageSize=20&siteid=1&pubflag=0&hiddenField=0'
    res = spider(url, headers)
    html = etree.HTML(res)
    chanId = html.xpath(
        '//div[@class="work-filter type-filter"]/ul/li/a/@href')[1:]
    type_name = html.xpath(
        '//div[@class="work-filter type-filter"]/ul/li/a/text()')[1:]
    for src in chanId:
        url = "http:" + src
        res = spider(url, headers)
        # print(html)
        html = etree.HTML(res)
        subCateId = html.xpath(
            '//div[@class="sub-type"]/dl[@class!="hidden"]/dd/a/@href')
        type_name = html.xpath(
            '//div[@class="sub-type"]/dl[@class!="hidden"]/dd/a/text()')
        for src, t_name in zip(subCateId, type_name):
            for i in range(1, 6):
                headers = {'User-Agent': random_user_agent()}
                url = "http:" + src + '&page=' + str(i)
                res = spider(url, headers)
                # print(html)
                html = etree.HTML(res)
                book_id_list = html.xpath(
                    '//div[@class="book-mid-info"]/h4/a/@href')
                name_list = html.xpath(
                    '//div[@class="book-mid-info"]/h4/a/text()')
                author_list = html.xpath(
                    '//p[@class="author"]/a[@class="name"]/text()')
                date = int(time.time())
                # print(type_list)
                # nums = html.xpath('//p[@class="update"]/span/span/text()')
                for name, author, book_id in zip(name_list, author_list,
                                                 book_id_list):
                    book_id = book_id.split('info/')[-1]
                    sql = "insert IGNORE into novels (book_id,name,author,type,date) values (%s,%s,%s,%s,%s)"
                    mysql.execute(sql, (book_id, name, author, t_name, date))
                    db.commit()
    return 'succ'


# def test():
#     # 打开数据库连接

#     sql = "select * from chapters where novel = %s"
#     mysql.execute(sql, ('不会真有人觉得修仙难吧'))
#     res = mysql.fetchall()
#     for i in res:
#         print(i)
#     # db.commit()
#     # 使用 cursor() 方法创建一个游标对象 cursor

#     # 使用 execute()  方法执行 SQL 查询

#     # 使用 fetchone() 方法获取单条数据.
#     # data = cursor.fetchone()
#     # sql='select * from novels'
#     # cursor.execute(sql)
#     # res=cursor.fetchone()
#     # print(res)
#     # print (" version : %s " % data)

#     # 关闭数据库连接
#     # db.close()

# if __name__ == '__main__':
#     db = pymysql.connect('localhost', 'root', '', 'qidian')
#     mysql = db.cursor()
#     # test()
#     run('1022899262')
#     # getType(sex='man')
#     # getType(sex='woman')

if __name__ == '__main__':
    app.run()