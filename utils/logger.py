# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :logger.py
# @Author     :
# @Describe   :

'''
进行日志的输出
'''
import os
import logging
import time
import re

from datetime import datetime, date
from logging.handlers import TimedRotatingFileHandler


# import fcntlock as fcntl
# from daily_rotating_file_handler import DailyRotatingFileHandler
#
# class MultiCompatibleTimedRotatingFileHandler(TimedRotatingFileHandler):
#
#     def doRollover(self):
#         if self.stream:
#             self.stream.close()
#             self.stream = None
#         # get the time that this sequence started at and make it a TimeTuple
#         currentTime = int(time.time())
#         dstNow = time.localtime(currentTime)[-1]
#         t = self.rolloverAt - self.interval
#         if self.utc:
#             timeTuple = time.gmtime(t)
#         else:
#             timeTuple = time.localtime(t)
#             dstThen = timeTuple[-1]
#             if dstNow != dstThen:
#                 if dstNow:
#                     addend = 3600
#                 else:
#                     addend = -3600
#                 timeTuple = time.localtime(t + addend)
#         dfn = self.baseFilename + "." + time.strftime(self.suffix, timeTuple)
#         # 兼容多进程并发 LOG_ROTATE
#         if not os.path.exists(dfn):
#             f = open(self.baseFilename, 'a')
#             fcntl.lock(f.fileno(), fcntl.LOCK_EX)
#             if os.path.exists(self.baseFilename):
#                 os.rename(self.baseFilename, dfn)
#         if self.backupCount > 0:
#             for s in self.getFilesToDelete():
#                 os.remove(s)
#         if not self.delay:
#             self.stream = self._open()
#         newRolloverAt = self.computeRollover(currentTime)
#         while newRolloverAt <= currentTime:
#             newRolloverAt = newRolloverAt + self.interval
#         # If DST changes and midnight or weekly rollover, adjust for this.
#         if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
#             dstAtRollover = time.localtime(newRolloverAt)[-1]
#             if dstNow != dstAtRollover:
#                 if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
#                     addend = -3600
#                 else:  # DST bows out before next rollover, so we need to add an hour
#                     addend = 3600
#                 newRolloverAt += addend
#         self.rolloverAt = newRolloverAt

def __singletion(cls):
    """
    单例模式的装饰器函数
    :param cls: 实体类
    :return: 返回实体类对象
    """
    instances = {}

    def getInstance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return getInstance


@__singletion
class MYLOG():
    # 分别指定输入的log的文件名,和log的名称
    def __init__(self, filename, logname, log_root_path=""):
        # 创建log对象,并且输出info以上的信息
        self.logger = logging.getLogger(logname)
        self.logger.setLevel(logging.DEBUG)
        self.logtype = filename
        self.log_root_path = log_root_path if log_root_path != "" else os.path.dirname(
            os.path.dirname(os.path.realpath(__file__)))

        # 创建Handler(控制台)
        consoleHandler = logging.StreamHandler()
        consoleHandler.setLevel(logging.DEBUG)
        # 创建Handler(文件)
        # 首先需要创建文件
        now = datetime.now()
        # now_format = now.strftime("%Y-%m-%d_%H-%M-%S")
        logfile_name = "{}".format(filename)
        # 判断./log文件夹是否存在,如果不存在则创建日志文件夹
        # log_root_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        if not os.path.exists(os.path.join(self.log_root_path, "log")):
            os.makedirs(os.path.join(self.log_root_path, "log"))

        logfile = os.path.join(os.path.join(self.log_root_path, "log"), logfile_name)
        # fileHandler = logging.FileHandler(logfile, encoding='UTF-8')
        # interval 滚动周期，
        # when="MIDNIGHT", interval=1 表示每天0点为更新点，每天生成一个文件
        # backupCount  表示日志保存个数,比如30
        fileHandler = TimedRotatingFileHandler(filename=logfile, when="MIDNIGHT", interval=1, delay=True, encoding="utf-8")
        # fileHandler = TimedRotatingFileHandler(filename=logfile, when="M", interval=1, delay=True,  encoding="utf-8")
        # fileHandler = MultiCompatibleTimedRotatingFileHandler(filename=logfile, when="MIDNIGHT", interval=1)
        fileHandler.suffix = "%Y-%m-%d"

        fileHandler.setLevel(logging.DEBUG)

        # 设置日志的输出格式
        formatter = logging.Formatter('%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s - %(message)s')
        fileHandler.setFormatter(formatter)
        consoleHandler.setFormatter(formatter)

        # 添加到Logger中
        self.logger.addHandler(consoleHandler)
        self.logger.addHandler(fileHandler)

        # 删除过期的日志
        # self.saveLogDays(log_expire_days)
        # self.saveLogDays(7)

    # 获取日志对象
    def getLogger(self):
        return self.logger

    # 控制保留几天的日志信息
    def saveLogDays(self, days=0):
        re_date = re.compile('{}-(\d+)-(\d+)-(\d+).log'.format(self.logtype))
        logfile = os.path.join(os.getcwd(), "log")
        now = date.today()
        # 首先判断是否需要删除以及日志文件是否存在
        if days > 0:
            if os.path.exists(logfile):
                for item in os.listdir(logfile):
                    try:
                        # 然后对这些文件切分出时间
                        date_list = re_date.findall(item)[0]
                        log_date = date(int(date_list[0]), int(date_list[1]), int(date_list[2]))
                        # 判断当前时间是否是小于7天的差距
                        if (now - log_date).days >= days:
                            os.remove(os.path.join(logfile, item))
                    except Exception as e:
                        pass
