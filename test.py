from flask import Flask, render_template, request
import pymysql
import requests
import random
import traceback
from lxml import etree
from requests.cookies import RequestsCookieJar
import time
from itertools import chain

app = Flask(__name__)
db = pymysql.connect('localhost', 'root', '', 'qidian')
mysql = db.cursor()


@app.route('/', methods=['GET', 'POST'])
def test():
    return 'hello world'


@app.route('/index')
def index():
    return render_template('index.html')


@app.route('/qidian')
def qidian():
    return render_template('qidian.html')


# 页面跳转
@app.route('/pages', methods=['GET'])
def pages():
    name = request.args.get('name')
    url = '/' + name
    return ({'code': 1, 'data': url})


@app.route('/novel')
def url():
    return render_template('novel.html')


# 初始化首页数据
@app.route('/init', methods=['GET'])
def init():
    # 获取上次更新时间
    sql1 = "select date from novels"
    mysql.execute(sql1)
    data = mysql.fetchone()
    # 转换为其他日期格式
    timeArray = time.localtime(data[0])
    res1 = time.strftime("%Y-%m-%d", timeArray)
    # 统计作品数量
    sql2 = "select count(*) from novels"
    mysql.execute(sql2)
    res2 = mysql.fetchone()
    # 整合所有类型
    sql3 = "select DISTINCT  type from novels group by type"
    mysql.execute(sql3)
    res3 = mysql.fetchall()
    resultlist = list(chain.from_iterable(res3))
    res3 = '、'.join(resultlist)
    # arr.append(res1)
    # result = [e + tuple(arr) for e in res3]
    check_list = get_checked()

    return ({
        'code': 1,
        'data1': res1,
        'data2': res2[0],
        'data3': res3,
        'check_list': check_list
    })


# 爬取所有小说信息到数据库
@app.route('/get_list', methods=['GET'])
def get_list():
    delete = clean_data()
    if delete is not None:
        return delete
    else:
        res = get_info()
        return res


# 添加作品检测
@app.route('/find_novel', methods=['GET', 'POST'])
def get_all():
    data = request.args.get('novel')
    sql = "select book_id,name from novels where name like %s"
    val = '%' + data + '%'
    mysql.execute(sql, (val))
    res = mysql.fetchall()
    res = list(res)
    return ({'code': 0, 'data': res})


# 获取作品检测结果
@app.route('/get_novel', methods=['GET'])
def get_novel():
    book_id = request.args.get('id')
    # get_content(book_id)
    # check_kw(book_id)
    novel_info = get_novel_info(book_id)
    check_list = get_checked()
    # bad_chap = get_bad(book_id)
    return ({
        'code': 1,
        'data': novel_info,
        'check_list': check_list,
    })


@app.route('/get_akw_list', methods=['GET'])
def get_akw_list():
    sql = "select key_word,count(key_word),count(distinct book_id) from bad_chap group by key_word"
    mysql.execute(sql)
    res = mysql.fetchall()
    print(res)
    # get_content(book_id)
    # check_kw(book_id)
    # bad_chap = get_bad(book_id)
    return ({'code': 1, 'data': res})

# 获取关键词作品列表
@app.route('/get_kw_novels', methods=['GET'])
def get_kw_novels():
    key_word = request.args.get('key_word')
    sql = "select novel,count(key_word) from bad_chap where key_word = %s group by key_word,novel"
    mysql.execute(sql, key_word)
    res = mysql.fetchall()
    return ({'code': 1, 'data': res})


# 保存存在问题
@app.route('/save_pro', methods=['GET'])
def save_pro():
    pro = request.args.get('pro')
    book_id = request.args.get('book_id')
    sql = "update checked set pro = %s where book_id=%s"
    res = mysql.execute(sql, (pro, book_id))
    db.commit()
    if (res):
        return ({'code': 1, 'data': '保存成功'})
    else:
        return ({'code': 0, 'data': '保存失败'})


# 敏感关键词查看
@app.route('/get_novel_kw_list', methods=['GET'])
def get_novel_kw_list():
    book_id = request.args.get('book_id')
    sql = "select key_word,count(key_word) from bad_chap where book_id = %s group by key_word"
    mysql.execute(sql, book_id)
    res = mysql.fetchall()
    print(res)
    return ({'code': 1, 'data': res})


# 敏感章节列表
@app.route('/get_chap_list', methods=['GET'])
def get_chap_list():
    book_id = request.args.get('book_id')
    key_word = request.args.get('key_word')
    sql = "select chapter,content from chapters where chapter in (select chapter from bad_chap where key_word = %s and book_id = %s)"
    mysql.execute(sql, (key_word, book_id))
    res = mysql.fetchall()
    # print(res)
    return ({'code': 1, 'data': res})


# 获取敏感关键词类型
@app.route('/get_kw_type', methods=['GET'])
def get_kw_type():
    key_word = request.args.get('key_word')
    sql = "select type from key_words where val = %s"
    mysql.execute(sql, key_word)
    res = mysql.fetchone()
    # print(res)
    return ({'code': 1, 'data': res[0]})


# 已检测作品结果
def get_checked():
    sql3 = "select count(*),sum(word_nums) from checked"
    mysql.execute(sql3)
    res1 = mysql.fetchone()
    sql4 = "select count(*) from chapters"
    mysql.execute(sql4)
    res2 = mysql.fetchone()
    sql4 = "select count(DISTINCT book_id),count(DISTINCT chapter),sum(DISTINCT word_nums) from bad_chap"
    mysql.execute(sql4)
    res3 = mysql.fetchone()
    check_list = list((*res1, *res2, *res3))
    return check_list


# 添加作品检测结果
def get_novel_info(book_id):
    sql = "select a.name,a.author,b.type,a.chap_nums,a.word_nums from checked a left join novels b on a.book_id=b.book_id where a.book_id  = %s"
    mysql.execute(sql, book_id)
    res1 = mysql.fetchone()
    sql = "select count(DISTINCT chapter) from bad_chap where book_id  = %s"
    mysql.execute(sql, book_id)
    res2 = mysql.fetchone()
    novel_info = list((*res1, *res2))
    print(novel_info)
    return novel_info


# 自动检测关键词
def check_kw(book_id):
    sql = "select novel,chapter,content from chapters where book_id = %s"
    mysql.execute(sql, book_id)
    chap_list = mysql.fetchall()
    for novel, tit, chap in chap_list:
        sql = "select val from key_words"
        mysql.execute(sql)
        word_list = mysql.fetchall()
        for word in word_list:
            if word[0] in chap:
                words = len(chap)
                word_nums = float(words) / 10000
                sql = "insert into bad_chap (book_id,novel,chapter,key_word,word_nums) values (%s,%s,%s,%s,%s)"
                mysql.execute(sql, (book_id, novel, tit, word[0], word_nums))
                db.commit()


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


# 重新爬取前清理相关数据
def clean_data():
    sql1 = "delete from novels"
    try:
        mysql.execute(sql1)
        db.commit()
    except Exception:
        return ({'code': 0, 'data': '重置数据失败'})


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
def get_content(book_id):
    headers = {'User-Agent': random_user_agent()}
    url = "https://book.qidian.com/info/" + book_id
    html = requests.get(url, headers=headers).text
    html = etree.HTML(html)
    name = html.xpath('//div[@class="book-info "]/h1/em/text()')  # 爬取书名
    author = html.xpath('//div[@class="book-info "]/h1/span/a/text()')  # 爬取作者名
    Lit_tit_list = html.xpath('//ul[@class="cf"]/li/a/text()')  # 爬取每个章节名字
    Lit_href_list = html.xpath('//ul[@class="cf"]/li/a/@href')  # 每个章节链接
    chap_nums = len(Lit_tit_list)
    # print(Lit_tit_list)
    # print(Lit_href_list)
    stop = 1
    word_nums = 0
    for tit, src in zip(Lit_tit_list, Lit_href_list):
        url = "http:" + src
        res = spider(url, headers)
        html = etree.HTML(res)
        text_list = html.xpath(
            '//div[@class="read-content j_readContent"]/p/text()')
        text = "".join(text_list).replace('　　', '')
        word_nums += len(text)
        print("正在抓取文章：" + tit)
        sql = "insert IGNORE into chapters (book_id,novel,chapter,content) values (%s,%s,%s,%s)"
        mysql.execute(sql, (book_id, name[0], tit, text))
        db.commit()
        if stop % 50 == 0:
            time.sleep(2)
            print('休息2秒')
        stop += 1
    word_nums = round(float(word_nums) / 10000, 2)
    sql = "insert into checked (book_id,name,author,chap_nums,word_nums) values (%s,%s,%s,%s,%s)"
    mysql.execute(sql, (book_id, name[0], author[0], chap_nums, word_nums))
    db.commit()
    return "爬取完成"


# 爬取各类型小说的信息
def get_info():
    res1 = getType('man')
    res2 = getType('woman')
    if res1 == 'succ' and res2 == 'succ':
        return ({'code': 1, 'data': '爬取成功'})
    else:
        return ({'code': 1, 'data': '爬取失败'})


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
            for i in range(1, 2):
                headers = {'User-Agent': random_user_agent()}
                url = "http:" + src + '&page=' + str(i)
                res = spider(url, headers)
                html = etree.HTML(res)
                book_id_list = html.xpath(
                    '//div[@class="book-mid-info"]/h4/a/@href')
                name_list = html.xpath(
                    '//div[@class="book-mid-info"]/h4/a/text()')
                # author_list = html.xpath(
                #     '//p[@class="author"]/a[@class="name"]/text()')
                date = int(time.time())
                for name, book_id in zip(name_list, book_id_list):
                    book_id = book_id.split('info/')[-1]
                    sql = "insert IGNORE into novels (book_id,name,type,date) values (%s,%s,%s,%s)"
                    mysql.execute(sql, (book_id, name, t_name, date))
                    db.commit()
    return 'succ'


if __name__ == '__main__':
    app.run()
