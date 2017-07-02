#!/usr/bin/python
# -*- coding: utf-8 -*-

import os,sys
import urllib.request,urllib.parse,json
import requests
import redis
import linecache
import time
# Create your tests here.


class WeiXin:
    def __init__(self, appid, secret, token_output="file", redis_host='127.0.0.1'):
        self.appid = appid
        self.secret = secret
        self.token_output = token_output
        if self.token_output == "redis":
            self.redis_conn = redis.Redis(host=redis_host, port=6379)

    # 获取token
    def get_token(self):
        url = "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=%s&secret=%s" % (self.appid,self.secret)
        token = json.loads(requests.get(url).text).get("access_token")
        return str(token).strip()

    # 检查token
    def check_token(self):
        if self.token_output == "redis":
            token = self.redis_conn.get('access_token') if self.redis_conn.exists('access_token') else False
            if token:
                return str(token, encoding="utf-8")
            else:
                token = self.redis_token(self.get_token())
                return str(token, encoding="utf-8").strip()
        else:
            filename = "wechat_session"
            token_file = sys.path[0] + "/" + filename
            token_time = int(linecache.getline(token_file,2)) if os.path.isfile(token_file) and os.path.getsize(token_file) else int(time.time())
            curr_time = int(time.time())
            token_exp = True if curr_time - token_time <= 7000 else False
            if os.path.exists(token_file) and token_exp:
                return str(linecache.getline(token_file,1)).strip()
            else:
                token=self.get_token()
                content=(token, str(time.time()).split(".")[0])
                self.save_to_file(filename,content,'normal','w')
                return token

    # 将token写入redis
    def redis_token(self, token):
        if not token or token == "":
            return False
        pipe = self.redis_conn.pipeline(transaction=True)
        self.redis_conn.setex('access_token',token,7000)
        token = self.redis_conn.get('access_token')
        return token

    # 将数据写入文件
    @staticmethod
    def save_to_file(filename="tempfile",content="",filetype='normal',opentype='w'):
        path=sys.path[0]
        # os_type=platform.system()
        curr_time=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
        if os.path.isdir(path):
            dir = path
        elif os.path.isfile(path):
            dir = os.path.dirname(path)
        if filetype.find('log') == -1:
            filepath = dir + "/" + filename
        else:
            logdir = path + "/logs/"
            if not os.path.isdir(logdir):
                os.mkdir(logdir)
            filepath = logdir + filename
        with open(filepath,opentype) as f:
            if filetype=="log":
                f.write("\n-------------------" + str(curr_time) + "-------------------\n")
            if isinstance(content,tuple):
                for res in content:
                    f.write(res)
                    f.write("\n")
            else:
                f.write(content)
                f.write("\n")
        return filepath

    # 获取所有用户openid列表
    def get_user_openid_list(self, nextid=""):
        url = "https://api.weixin.qq.com/cgi-bin/user/get?access_token=%s" % (self.check_token())
        req = json.loads(requests.get(url).text)
        if "errocode" in req.keys() or "errmsg" in req.keys():
            return "error: token验证失败,请检查token是否有效"
        else:
            return req.get('data').get('openid')

    # 通过用户的昵称获取openid等相关信息
    def get_user_openid(self, nickname=""):
        token = self.check_token()
        if nickname == "" or not nickname:
            return "error: 微信朋友不能为空,若有多个，用分号隔开"
        userlist=self.get_user_openid_list()
        f_list = list(set(nickname.split(';')))
        if isinstance(userlist,str) and "error:" in userlist:
            return userlist
        i, j, k, f_openid = 0, 0, False, []
        for i in range(len(userlist)):
            url = "https://api.weixin.qq.com/cgi-bin/user/info?access_token=%s&openid=%s&lang=zh_CN" % (token,userlist[i])
            userinfo = json.loads(requests.get(url).text)
            for j in range(len(f_list)):
                if userinfo.get('nickname') == f_list[0]:
                    f_openid.append(userinfo.get('openid'))
                    k = k+1
                    break
            if k == len(f_list):
                break
        res = f_openid if f_openid else "error: 未找到指定的微信用户，请检查该微信用户是否已关注本公众号"
        return res

    # 获取信息模板编号
    def get_template_number(self):
        token = self.check_token()
        url="https://api.weixin.qq.com/cgi-bin/template/get_all_private_template?access_token=%s" % (token)
        html=urllib.request.urlopen(url)
        req=json.loads(html.read().decode())
        return req

    # 发送模板信息
    def send_template_msg(self, friend, friend_type=1, content="", template_id=""):
        url = "https://api.weixin.qq.com/cgi-bin/message/template/send?access_token=%s" % (self.check_token())
        if friend_type == 1:
            openid = list(set(friend.split(';')))
        else:
            f = self.get_user_openid(friend)
            openid = f if isinstance(f, list) else f
        j = 0
        msg={
                   "first": {
                       "value":"----------------------报警提示----------------------",
                       "color":"#ff0000"
                   },
                   "keyword3": {
                       "value":content,
                       "color":"#ff0000"
                   }
           }

        if openid:
            for i in range(len(openid)):
                data = {"touser":openid[i],"template_id":template_id,"data":msg }
                log = self.post_data(url, data)
                self.save_to_file('wechat.log',log,'log','a')
                j = j + 1
            return "message: 一共发送了" + str(j) + "位微信朋友，详情查看日志!"
        else:
            return "error: 微信用户有误，数据推送失败!"

    # 提交post数据
    def post_data(self,url,data):
        data = json.dumps(data)
        res = requests.post(url=url, data=data)
        return res.text

''' 示例演示
appid='开发者ID'
secret='开发者密码'
token_output='file'        //默认将 token 存在file中，如果需要将token存入redis; 改成token_output='redis'即可
redis_host='127.0.0.1'     //如果将token存入redis中，此项就必须要配置
template_id='模板id'       //通过模板信息中就能查到，发送报警的好像是 9Br7-3WFw10pCRJEJHLF5ZBf4Z-zOVuLOJ4qRbSwwR8
friend = "openid"                //信息接收者的微信识别号，这里需要填写openid或者填写昵称，最好用openid,昵称查询太慢，如果有多个用;分号隔开
friend_type = 1            //默认为1，为1时，就是用openid发送，不为1时，用昵称发送
content="实际要发送的内容"  //实际要发送的内容,为json格式，请参考自己所选择的模板，进行内容编排

wx=WeiXin(appid=appid,secret=secret)
c=wx.send_template_msg(friend, 2, content, template_id)
print(c)
'''

