#!/usr/bin/env python3
"""
无sudo权限下获取中国北京时间（NTP），仅用于进程内时间校准
"""
import ntplib
from datetime import datetime, timedelta, timezone

def get_beijing_time():
    try:
        c = ntplib.NTPClient()
        response = c.request('ntp.ntsc.ac.cn', version=3, timeout=5)
        utc_dt = datetime.utcfromtimestamp(response.tx_time).replace(tzinfo=timezone.utc)
        beijing_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
        return beijing_dt
    except Exception as e:
        print(f"获取NTP时间失败: {e}")
        return None

if __name__ == '__main__':
    bj_time = get_beijing_time()
    if bj_time:
        print("北京时间：", bj_time.strftime('%Y-%m-%d %H:%M:%S'))
    else:
        print("无法获取北京时间") 