from flask import Flask, render_template, request
import pymysql
import requests
import random
import traceback
from lxml import etree
from requests.cookies import RequestsCookieJar
import time
from itertools import chain
from operator import itemgetter  # itemgetter用来去dict中的key，省去了使用lambda函数
from itertools import groupby  # itertool还包含有其他很多函数，比如将多个list联合起来
# import threading

app = Flask(__name__)
db = pymysql.connect('localhost', 'root', '', 'qidian')
mysql = db.cursor()
novle_pro = 0
batch_pro = 0
is_running = 1
is_batch = 1
crawling = 1

# lock = threading.Lock()


@app.route('/')
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
    db.ping(reconnect=True)
    mysql.execute(sql1)
    data = mysql.fetchone()
    if data:
        # 转换为其他日期格式
        timeArray = time.localtime(data[0])
        res1 = time.strftime("%Y-%m-%d ", timeArray)
    else:
        res1 = ''
    # 统计作品数量
    sql2 = "select count(*) from novels"
    db.ping(reconnect=True)
    mysql.execute(sql2)
    res2 = mysql.fetchone()
    # 整合所有类型
    sql3 = "select DISTINCT  type from novels group by type"
    db.ping(reconnect=True)
    mysql.execute(sql3)
    res3 = mysql.fetchall()
    if res3:
        resultlist = list(chain.from_iterable(res3))
        res3 = '、'.join(resultlist)
    # arr.append(res1)
    # result = [e + tuple(arr) for e in res3]
    check_list = get_checked()
    datetime = get_datetime()

    return ({
        'code': 1,
        'data1': res1,
        'data2': res2[0],
        'data3': res3,
        'check_list': check_list,
        'datetime': datetime
    })


# 筛选已检测作品结果
@app.route('/update_list', methods=['GET'])
def update_list():
    data = request.args.get('datetime')
    sql1 = "select count(*),sum(word_nums) from checked where datetime = %s"
    sql2 = "select count(*) from chapters where book_id in (select book_id from checked where datetime = %s)"
    sql3 = "select count(DISTINCT book_id),count(DISTINCT chapter),sum(DISTINCT word_nums) from bad_chap where book_id in (select book_id from checked where datetime = %s)"
    sql4 = "select type from novels where book_id in (select book_id from checked where datetime = %s)"
    # lock.acquire()
    try:
        db.ping(reconnect=True)
        mysql.execute(sql1, data)
        res1 = mysql.fetchone()
        mysql.execute(sql2, data)
        res2 = mysql.fetchone()
        mysql.execute(sql3, data)
        res3 = mysql.fetchone()
        mysql.execute(sql4, data)
        res4 = mysql.fetchone()
    except Exception as e:
        db.rollback()  # 事务回滚
        print('事务处理失败', e)
    else:
        check_list = list((*res1, *res2, *res3, *res4))
        print(check_list)
        return ({'code': 1, 'check_list': check_list})


# 爬取所有小说信息到数据库
@app.route('/get_list', methods=['GET'])
def get_list():
    clean_data()
    res = get_info()
    return res


# 添加作品检测
@app.route('/find_novel', methods=['GET', 'POST'])
def get_all():
    data = request.args.get('novel')
    sql = "select book_id,name from novels where name like %s"
    val = '%' + data + '%'
    db.ping(reconnect=True)
    mysql.execute(sql, (val))
    res = mysql.fetchall()
    res = list(res)
    return ({'code': 0, 'data': res})


# 批量检测
@app.route('/get_batch', methods=['GET'])
def get_batch():
    data = request.args.get('type')
    delete_batch(data)
    sql = "select book_id from novels where type = %s"
    db.ping(reconnect=True)
    mysql.execute(sql, data)
    res = mysql.fetchall()
    length = len(res)
    stop = 0
    timestr = int(time.time())
    timeArray = time.localtime(timestr)
    datetime = time.strftime("%Y-%m-%d %H:%M", timeArray)
    global batch_pro
    for book in res:
        book_id = str(book[0])
        # print(book_id)
        spider = get_content(book_id, datetime)
        stop += 1
        batch_pro = int(stop / length * 100)
        if spider == 'fail':
            return ({
                'code': 0,
                'data': "检索失败",
            })
    return ({
        'code': 1,
        'data': "检索成功",
    })


# 获取作品检测结果
@app.route('/get_novel', methods=['GET'])
def get_novel():
    book_id = request.args.get('id')
    delete_one(book_id)
    timestr = int(time.time())
    timeArray = time.localtime(timestr)
    datetime = time.strftime("%Y-%m-%d %H:%M", timeArray)
    spider = get_content(book_id, datetime)
    if spider == '爬取中断':
        return ({
            'code': 0,
            'data': "",
        })
    else:
        novel_info = get_novel_info(book_id)
        check_list = get_checked()
        # bad_chap = get_bad(book_id)
        return ({
            'code': 1,
            'data': novel_info,
            'check_list': check_list,
        })


# 取消检索
@app.route('/delete_novel', methods=['GET'])
def delete_novel():
    global is_running
    is_running = 0
    time.sleep(1)
    book_id = request.args.get('id')
    delete_one(book_id)
    is_running = 1
    return ({'code': 1, 'data': '取消成功'})


# 取消批量检索
@app.route('/cancel_batch', methods=['GET'])
def cancel_batch():
    global is_batch
    is_batch = 0
    time.sleep(1)
    batch_type = request.args.get('type')
    delete_batch(batch_type)
    is_batch = 1
    return ({'code': 1, 'data': '取消成功'})


# 取消重新爬取
@app.route('/cancel_re', methods=['GET'])
def cancel_re():
    global crawling
    crawling = 0
    time.sleep(1)
    crawling = 1


# 获取类型列表
@app.route('/get_type_list', methods=['GET'])
def get_type_list():
    sql = "select style,type FROM novels GROUP BY style,type"
    db.ping(reconnect=True)
    mysql.execute(sql)
    lst = list(mysql.fetchall())
    lst.sort(key=itemgetter(0))  #需要先排序，然后才能groupby。lst排序后自身被改变
    lstg = groupby(lst, itemgetter(0))
    res = [(key, list(group)) for key, group in lstg]
    for i in range(len(res)):
        arr = []
        for j in res[i][1]:
            arr.append(j[1])
        res[i] = list(res[i])
        res[i][1] = arr
    return ({'code': 1, 'data': res})


# 获取检测进度
@app.route('/get_novel_pro', methods=['GET'])
def get_novel_pro():
    return ({'code': 1, 'data': novle_pro})


# 获取批量检测进度
@app.route('/get_batch_pro', methods=['GET'])
def get_batch_pro():
    return ({'code': 1, 'data': batch_pro})


# 获取关键词检索列表
@app.route('/get_akw_list', methods=['GET'])
def get_akw_list():
    sql = "select key_word,count(key_word),count(distinct book_id) from bad_chap group by key_word order by count(key_word) DESC,count(distinct book_id) DESC"
    db.ping(reconnect=True)
    mysql.execute(sql)
    res = mysql.fetchall()
    # print(res)
    # get_content(book_id)
    # check_kw(book_id)
    # bad_chap = get_bad(book_id)
    return ({'code': 1, 'data': res})


# 获取关键词作品列表
@app.route('/get_kw_novels', methods=['GET'])
def get_kw_novels():
    key_word = request.args.get('key_word')
    sql = "select novel,author,count(key_word) from bad_chap where key_word = %s group by key_word,novel,author order by count(key_word) desc"
    db.ping(reconnect=True)
    mysql.execute(sql, key_word)
    res = mysql.fetchall()
    # print(res)
    return ({'code': 1, 'data': res})


# 获取关键词作品章节列表
@app.route('/get_kw_chaps', methods=['GET'])
def get_kw_chaps():
    key_word = request.args.get('key_word')
    novel = request.args.get('novel')
    sql = "select chapter,content from chapters where chapter in (select chapter from bad_chap where key_word = %s and novel = %s)"
    db.ping(reconnect=True)
    mysql.execute(sql, (key_word, novel))
    res = mysql.fetchall()
    # print(res)
    return ({'code': 1, 'data': res})


# 保存存在问题
@app.route('/save_pro', methods=['GET'])
def save_pro():
    pro = request.args.get('pro')
    book_id = request.args.get('book_id')
    print(pro)
    print(book_id)
    sql = "update checked set pro=%s where book_id=%s"
    db.ping(reconnect=True)
    mysql.execute(sql, (pro, book_id))
    db.commit()
    return ({'code': 1, 'data': '保存成功'})


# 敏感关键词查看
@app.route('/get_novel_kw_list', methods=['GET'])
def get_novel_kw_list():
    book_id = request.args.get('book_id')
    sql = "select key_word,count(key_word) from bad_chap where book_id = %s group by key_word"
    db.ping(reconnect=True)
    mysql.execute(sql, book_id)
    res = mysql.fetchall()
    # print(res)
    return ({'code': 1, 'data': res})


# 敏感章节列表
@app.route('/get_chap_list', methods=['GET'])
def get_chap_list():
    book_id = request.args.get('book_id')
    key_word = request.args.get('key_word')
    sql = "select chapter,content from chapters where chapter in (select chapter from bad_chap where key_word = %s and book_id = %s)"
    db.ping(reconnect=True)
    mysql.execute(sql, (key_word, book_id))
    res = mysql.fetchall()
    # print(res)
    return ({'code': 1, 'data': res})


# 获取敏感关键词类型
@app.route('/get_kw_type', methods=['GET'])
def get_kw_type():
    key_word = request.args.get('key_word')
    sql = "select type from key_words where val = %s"
    db.ping(reconnect=True)
    mysql.execute(sql, key_word)
    res = mysql.fetchone()
    # print(res)
    return ({'code': 1, 'data': res[0]})


# 获取人工检测小说列表
@app.route('/get_man_novels', methods=['GET'])
def get_man_novels():
    sql = "select book_id,name from checked"
    db.ping(reconnect=True)
    mysql.execute(sql)
    res = mysql.fetchall()
    # print(res)
    return ({'code': 1, 'data': res})


# 获取人工检测列表
@app.route('/get_man_check', methods=['GET'])
def get_man_check():
    mkw = request.args.get('mkw')
    book_id = request.args.get('novel')
    kws = mkw.split('/')
    sql = "select novel,chapter,content from chapters where book_id = %s"
    db.ping(reconnect=True)
    mysql.execute(sql, book_id)
    chap_list = mysql.fetchall()
    res_list = []
    for word in kws:
        res = [word]
        count = 0
        for novel, tit, chap in chap_list:
            if word in chap:
                count += 1
        res.append(count)
        res_list.append(res)
    novel_info = get_novel_info(book_id)
    return ({'code': 1, 'data': res_list, 'novel_info': novel_info})


# 获取人工检测章节列表
@app.route('/get_man_chaps', methods=['GET'])
def get_man_chap():
    key_word = request.args.get('key_word')
    book_id = request.args.get('book_id')
    sql = "select chapter,content from chapters where book_id = %s"
    db.ping(reconnect=True)
    mysql.execute(sql, book_id)
    chap_list = mysql.fetchall()
    chaps = []
    for tit, chap in chap_list:
        if key_word in chap:
            arr = []
            arr.append(tit)
            arr.append(chap)
            chaps.append(arr)
    return ({'code': 1, 'data': chaps})


# 获取综合评定信息
@app.route('/get_judge', methods=['GET'])
def get_judge():
    sql = "select count(*) from checked union select count(*) from chapters union select sum(word_nums) from checked"
    db.ping(reconnect=True)
    mysql.execute(sql)
    res = mysql.fetchall()
    res = list(chain.from_iterable(res))
    n_count = res[0]
    c_count = res[1]
    w_count = res[2]
    # 问题作品占比
    sql = "select count(distinct novel) from bad_chap"
    db.ping(reconnect=True)
    mysql.execute(sql)
    bad_n = mysql.fetchone()
    n_score = novel_score(bad_n[0], n_count)
    # print(n_score)
    sql = "select name,author from checked"
    db.ping(reconnect=True)
    mysql.execute(sql)
    res = mysql.fetchall()
    arr1 = []
    for novel in res:
        arr = []
        arr.append(novel[0])
        arr.append(novel[1])
        sql = "select chapter,count(distinct chapter),word_nums from bad_chap where novel = %s group by chapter,word_nums"
        db.ping(reconnect=True)
        mysql.execute(sql, novel[0])
        res = mysql.fetchall()
        # print(res)
        # 问题章节
        c_num = len(res)
        c_score = chap_score(c_num, c_count)
        #         sql = "select count(distinct chapter)from bad_chap where novel = %s"
        # db.ping(reconnect=True) mysql.execute(sql, novel)
        # res = mysql.fetchone()
        w_num = 0.00
        for i in res:
            w_num += i[2]
        wd_score = w_score(w_num, w_count)
        score = n_score + c_score + wd_score
        arr.append(score)
        if arr[2] > 12:
            arr.append('A')
        elif arr[2] > 9 and arr[2] <= 12:
            arr.append('B')
        elif arr[2] > 6 and arr[2] <= 9:
            arr.append('C')
        else:
            arr.append('D')
        arr1.append(arr)
    t = sum(arr1, [])
    grade = get_grade(n_count, t.count('C'), t.count('D'))
    chart = [[t.count('A'), 'A级作品'], [t.count('B'), 'B级作品'],
             [t.count('C'), 'C级作品'], [t.count('D'), 'D级作品']]
    # print(arr1)
    return ({'code': 1, 'data': arr1, 'chart': chart, 'grade': grade})


# 获取检测日期列表
def get_datetime():
    sql = "select distinct datetime from checked order by datetime desc"
    db.ping(reconnect=True)
    mysql.execute(sql)
    res = mysql.fetchall()
    arr = []
    for i in res:
        arr.append(i[0])
    return arr


# 删除爬取过的单个文章内容
def delete_one(book_id):
    sql1 = "delete from chapters where book_id = %s"
    sql2 = "delete from bad_chap where book_id = %s"
    sql3 = "delete from checked where book_id = %s"
    # lock.acquire()
    try:
        mysql.execute(sql1, book_id)
        mysql.execute(sql2, book_id)
        mysql.execute(sql3, book_id)
    except Exception as e:
        db.rollback()  # 事务回滚
        print('事务处理失败', e)
    else:
        db.commit()  # 事务提交
        print('事务处理成功', mysql.rowcount)


# 删除单个类型作品
def delete_batch(batch_type):
    sql1 = "delete FROM chapters WHERE book_id in(SELECT book_id FROM novels where type = %s)"
    sql2 = "delete FROM bad_chap WHERE book_id in(SELECT book_id FROM novels where type = %s)"
    sql3 = "delete FROM checked WHERE book_id in(SELECT book_id FROM novels where type = %s)"
    # lock.acquire()
    try:
        mysql.execute(sql1, batch_type)
        mysql.execute(sql2, batch_type)
        mysql.execute(sql3, batch_type)
    except Exception as e:
        db.rollback()  # 事务回滚
        print('事务处理失败', e)
    else:
        db.commit()  # 事务提交
        print('事务处理成功', mysql.rowcount)


# 综合评价
def get_grade(data, c, d):
    cc = float(c / data)
    dd = float(d / data)
    if cc <= 0.2 and dd <= 0.1:
        return '优秀'
    elif cc <= 0.3 and cc > 0.2 and dd <= 0.1:
        return '较优秀'
    elif cc <= 0.3 and dd > 0.1 and dd < 0.2:
        return '中等'
    elif cc <= 0.4 and cc > 0.3 and dd < 0.2:
        return '较严重'
    else:
        return '严重'

    # print(res)

    # print(res)

    # for tit, chap in chap_list:
    #     if key_word in chap:
    #         arr = []
    #         arr.append(tit)
    #         arr.append(chap)
    #         chaps.append(arr)
    # return ({'code': 1, 'data': chaps})


# 小说/章节得分
def novel_score(a, b):
    num = float(int(a) / b)
    if num <= 0.5:
        return 8
    elif num > 0.5 and num <= 1:
        return 4
    elif num > 1 and num <= 2:
        return 1
    else:
        return 0


# 章节得分
def chap_score(a, b):
    num = float(int(a) / b)
    if num <= 0.05:
        return 8
    elif num > 0.05 and num <= 0.1:
        return 4
    elif num > 0.1 and num <= 0.5:
        return 1
    else:
        return 0


# 字数得分
def w_score(a, b):
    num = float(a / b)
    if num <= 0.005:
        return 8
    elif num > 0.005 and num <= 0.01:
        return 4
    elif num > 0.01 and num <= 0.05:
        return 1
    else:
        return 0


# 已检测作品结果
def get_checked():
    # sql3 = "select count(*),sum(word_nums) from checked"
    # db.ping(reconnect=True)
    # mysql.execute(sql3)
    # res1 = mysql.fetchone()
    # sql4 = "select count(*) from chapters"
    # db.ping(reconnect=True)
    # mysql.execute(sql4)
    # res2 = mysql.fetchone()
    # sql4 = "select count(DISTINCT book_id),count(DISTINCT chapter),sum(DISTINCT word_nums) from bad_chap"
    # db.ping(reconnect=True)
    # mysql.execute(sql4)
    # res3 = mysql.fetchone()
    # check_list = list((*res1, *res2, *res3))
    # return check_list

    sql1 = "select count(*),sum(word_nums) from checked"
    sql2 = "select count(*) from chapters"
    sql3 = "select count(DISTINCT book_id),count(DISTINCT chapter),sum(DISTINCT word_nums) from bad_chap"
    sql4 = "select distinct type from novels where book_id in (select book_id from checked)"
    # lock.acquire()
    try:
        db.ping(reconnect=True)
        mysql.execute(sql1)
        res1 = mysql.fetchone()
        mysql.execute(sql2)
        res2 = mysql.fetchone()
        mysql.execute(sql3)
        res3 = mysql.fetchone()
        mysql.execute(sql4)
        res4 = mysql.fetchall()
        res4 = "、".join(list(chain.from_iterable(res4))) 
        print(res4)
    except Exception as e:
        db.rollback()  # 事务回滚
        print('事务处理失败', e)
    else:
        check_list = list((*res1, *res2, *res3))
        check_list.append(res4)
        return check_list


# 添加作品检测结果
def get_novel_info(book_id):
    sql = "select a.name,a.author,b.type,a.chap_nums,a.word_nums,a.pro from checked a left join novels b on a.book_id=b.book_id where a.book_id  = %s"
    db.ping(reconnect=True)
    mysql.execute(sql, book_id)
    res1 = mysql.fetchone()
    sql = "select count(DISTINCT chapter) from bad_chap where book_id  = %s"
    db.ping(reconnect=True)
    mysql.execute(sql, book_id)
    res2 = mysql.fetchone()
    novel_info = list((*res1, *res2))
    print(novel_info)
    return novel_info


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
    sql1 = "delete from novels_copy"
    sql2 = "truncate table novels_copy"
    # lock.acquire()
    try:
        mysql.execute(sql1)
        mysql.execute(sql2)
    except Exception as e:
        db.rollback()  # 事务回滚
        print('事务处理失败', e)
    else:
        db.commit()  # 事务提交
        print('事务处理成功', mysql.rowcount)


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
def get_content(book_id, datetime):
    headers = {'User-Agent': random_user_agent()}
    url = "https://book.qidian.com/info/" + book_id
    html = requests.get(url, headers=headers).text
    html = etree.HTML(html)
    names = html.xpath('//div[@class="book-info "]/h1/em/text()')  # 爬取书名
    if names != []:
        name = names[0]
        print(name)
        author = html.xpath('//div[@class="book-info "]/h1/span/a/text()')[
            0]  # 爬取作者名
        Lit_tit_list = html.xpath('//ul[@class="cf"]/li/a/text()')  # 爬取每个章节名字
        Lit_href_list = html.xpath('//ul[@class="cf"]/li/a/@href')  # 每个章节链接
        chap_nums = len(Lit_tit_list)
        # print(Lit_tit_list)
        # print(Lit_href_list)
        stop = 0
        word_nums = 0
        global novle_pro
        for tit, src in zip(Lit_tit_list, Lit_href_list):
            global is_running
            global is_batch
            if is_running == 1 and is_batch == 1:
                stop += 1
                url = "http:" + src
                res = spider(url, headers)
                html = etree.HTML(res)
                if url[7:10] == 'vip':
                    text_list = html.xpath(
                        '//div[contains(@class, "read-content")]/p/text()')
                else:
                    text_list = html.xpath(
                        '//div[@class="read-content j_readContent"]/p/text()')
                text = "".join(text_list).replace('　　', '')
                single_nums = len(text)
                word_nums += single_nums
                # print(word_nums)
                # print("正在抓取：" + tit)
                novle_pro = int(stop / chap_nums * 100)
                # print(novle_pro)
                sql = "insert IGNORE into chapters (book_id,novel,chapter,content) values (%s,%s,%s,%s)"
                db.ping(reconnect=True)
                mysql.execute(sql, (book_id, name, tit, text))
                db.commit()

                sql = "select val from key_words"
                db.ping(reconnect=True)
                mysql.execute(sql)
                word_list = mysql.fetchall()
                for word in word_list:
                    if word[0] in text:
                        w_nums = float(single_nums) / 10000
                        sql = "insert into bad_chap (book_id,novel,author,chapter,key_word,word_nums) values (%s,%s,%s,%s,%s,%s)"
                        db.ping(reconnect=True)
                        mysql.execute(
                            sql, (book_id, name, author, tit, word[0], w_nums))
                        db.commit()

                if stop % 50 == 0:
                    time.sleep(2)
            else:
                return 'fail'
        word_nums = round(float(word_nums) / 10000, 2)
        sql = "insert into checked (book_id,name,author,chap_nums,word_nums,datetime) values (%s,%s,%s,%s,%s,%s)"
        db.ping(reconnect=True)
        mysql.execute(sql,
                      (book_id, name, author, chap_nums, word_nums, datetime))
        db.commit()
        return "爬取完成"


# 爬取各类型小说的信息
def get_info():
    res1 = getType('man')
    res2 = getType('woman')
    if res1 == 'succ' and res2 == 'succ':
        sql1 = "delete from novels"
        sql2 = "INSERT INTO novels SELECT * FROM novels_copy"
        # lock.acquire()
        try:
            mysql.execute(sql1)
            mysql.execute(sql2)
        except Exception as e:
            db.rollback()  # 事务回滚
            print('事务处理失败', e)
        else:
            db.commit()  # 事务提交
            print('事务处理成功', mysql.rowcount)
        return ({'code': 1, 'data': '爬取成功'})
    else:
        return ({'code': 0, 'data': '爬取失败'})


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
    style_name = html.xpath(
        '//div[@class="work-filter type-filter"]/ul/li/a/text()')[1:]
    for src, style in zip(chanId, style_name):
        url = "http:" + src
        res = spider(url, headers)
        print(style)
        html = etree.HTML(res)
        subCateId = html.xpath(
            '//div[@class="sub-type"]/dl[@class!="hidden"]/dd/a/@href')
        type_name = html.xpath(
            '//div[@class="sub-type"]/dl[@class!="hidden"]/dd/a/text()')
        for src, t_name in zip(subCateId, type_name):
            print(t_name)
            for i in range(1, 6):
                global crawling
                if crawling == 1:
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
                        sql = "insert ignore into novels_copy (book_id,name,type,date,style) values (%s,%s,%s,%s,%s)"
                        db.ping(reconnect=True)
                        mysql.execute(sql,
                                      (book_id, name, t_name, date, style))
                        db.commit()
                else:
                    return 'fail'
    return 'succ'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port='80')
