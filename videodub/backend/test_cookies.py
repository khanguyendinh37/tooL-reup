from app.core.downloader import validate_cookies_content

cookies = """# Netscape HTTP Cookie File
# http://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file!  Do not edit.

www.douyin.com    FALSE    /jingxuan    FALSE    0        douyin.com
www.douyin.com    FALSE    /user    FALSE    0        douyin.com
www.douyin.com    FALSE    /user    FALSE    0    device_web_cpu_core    16
www.douyin.com    FALSE    /user    FALSE    0    device_web_memory_size    16
www.douyin.com    FALSE    /user    FALSE    0    architecture    amd64
.douyin.com    TRUE    /    TRUE    1819026126    enter_pc_once    1
.douyin.com    TRUE    /    TRUE    1800344631    UIFID_TEMP    5bdad390e71fd6e6e69e3cafe6018169c2447c8bc0b8484cc0f203a274f99fdb3a985f91097b979832b5297e1c5ec505e3d2362a9af1ed3439b41307e1a9556dae643e20eb36f5c6da330224bedf573f30be7292f9ecd4060419070f1a87409e38db943d19911b006a035f307d21c1ee
.douyin.com    TRUE    /    TRUE    1819026127    hevc_supported    true
www.douyin.com    FALSE    /    TRUE    1800344637    fpk1    U2FsdGVkX1+oiqjdUlfLJESjvSUC10GGEY/vRZdf6K08zCAAt/Ep5LzEF0NgmuqzWs2QAQSKxpXMoyTnSGI1iw==
www.douyin.com    FALSE    /    TRUE    1800344637    fpk2    89db729cfcdc129111f017b0e7ac324a
.douyin.com    TRUE    /    TRUE    1803565343    UIFID    5bdad390e71fd6e6e69e3cafe6018169c2447c8bc0b8484cc0f203a274f99fdb45ae6cd79e009293c925b12beb10a579c375d3677594441259c4b4343318e848349b97974d9ffcc31bb69359dae17e69d1af93c8cda0093a0fc965914cbc791a49a5c72b292e3907187401e2643215e15c1beb43a7ff3e6fc6c2e0ac71e125dfebf0bb2c03312f12a205b39e49b0662e960f59a7b93534522d2ac2a0754c2da2
.douyin.com    TRUE    /    FALSE    1789650127    bd_ticket_guard_client_web_domain    2
.douyin.com    TRUE    /    TRUE    1810179761    d_ticket    86c177d7a8a19c6fe1e79d280f750828d410d
.douyin.com    TRUE    /    TRUE    1813203762    passport_assist_user    CkF1ON4eJJ5WnOGf8pk8DKz4MYZDH4KZChxqjHD8f3eWE3vxMQONrxnt6nGkN_RZq3Jc1MLgGOukEvJIZ9Jfm4C8IxpKCjwAAAAAAAAAAAAAUGrR5jUxoWb4s6dB8umVFDm7t6vu-PWzx1Ad2o6tTUZxjQq6tyKOrLvx_hn1xbkLzpsQhKmRDhiJr9ZUIAEiAQNcutkS
.douyin.com    TRUE    /    FALSE    1789011762    n_mh    LOaYnuV_m4mNyiWYEQYtdvt4vzNW43YVvIGiXbM8ZAE
.douyin.com    TRUE    /    TRUE    1787711863    uid_tt    dfd3fb3248b8ff9d03f98440d49c3d78
.douyin.com    TRUE    /    TRUE    1787711863    uid_tt_ss    dfd3fb3248b8ff9d03f98440d49c3d78
.douyin.com    TRUE    /    TRUE    1787711863    sid_tt    0323087541144a1600c57672e7d59eab
.douyin.com    TRUE    /    TRUE    1787711863    sessionid    0323087541144a1600c57672e7d59eab
.douyin.com    TRUE    /    TRUE    1787711863    sessionid_ss    0323087541144a1600c57672e7d59eab
.douyin.com    TRUE    /    TRUE    1787711863    is_staff_user    false
.douyin.com    TRUE    /    TRUE    1787711863    has_biz_token    false
.douyin.com    TRUE    /    FALSE    1788165710    _bd_ticket_crypt_cookie    1d14e8afa48c56382310ee18707a4fb3
.douyin.com    TRUE    /    FALSE    1813203762    login_time    1778643762527
.douyin.com    TRUE    /    FALSE    1813204872    __live_version__    %221.1.5.1831%22
.douyin.com    TRUE    /    FALSE    1813206014    live_use_vvc    %22false%22
live.douyin.com    FALSE    /    TRUE    1813204875    fpk1    U2FsdGVkX19GfNssXAxv/Y6BPYISVEdaszj099G0MGIZqu6EHpBbLBJauLkwm6TwnVglE5YxtI2zz3FA2aNArA==
live.douyin.com    FALSE    /    TRUE    1813204875    fpk2    b87543ecbc0ba610d9f06f9f2c432a46
.douyin.com    TRUE    /    FALSE    1813206014    live_debug_info    %7B%22roomId%22%3A%227639209153898744628%22%2C%22resolution%22%3A%7B%22width%22%3A480%2C%22height%22%3A846%7D%2C%22fps%22%3A79%2C%22audioDataRate%22%3A44100%2C%22droppedFrames%22%3A0%2C%22totalFrames%22%3A1%2C%22videoBuffer%22%3A%5B%5D%2C%22src%22%3A%22https%3A%2F%2Fpull-flv-t13.douyincdn.com%2Fstage%2Fstream-695823396121871159_Stage0T000ld5.flv%3Fexpire%3D1779250799%26sign%3D9ca0d02d020fe395ee85e1d18e3d6865%26arch_hrchy%3Dh1%26exp_hrchy%3Dh1%26neq%3D1%26major_anchor_level%3Dcommon%26unique_id%3Dstream-695823396121871159_823_flv_Stage0T000ld5%26t_id%3D037-202605131219582B9B67E232CE212103A9-5OhXOl%26_session_id%3D037-202605131219582B9B67E232CE212103A9-5OhXOl.1778646014714.86764%26rsi%3D1%26abr_pts%3D-800%22%2C%22linkmicInfo%22%3A%7B%22uiLayout%22%3A0%2C%22playModes%22%3A%5B%5D%2C%22allDevices%22%3A%22%EF%BC%88%E8%BF%9E%E7%BA%BF%E8%AE%BE%E5%A4%87%EF%BC%89%EF%BC%9A%E7%94%B3%E8%AF%B7%E8%BF%9E%E7%BA%BF%E5%90%8E%E6%89%8D%E8%8E%B7%E5%8F%96%22%2C%22audioInputs%22%3A%5B%5D%2C%22videoInputs%22%3A%5B%5D%7D%2C%22href%22%3A%22https%3A%2F%2Flive.douyin.com%2F252397310331%3Fanchor_id%3D1266269050896472%22%7D
.douyin.com    TRUE    /    FALSE    1813206041    PhoneResumeUidCacheV1    %7B%221408940327830329%22%3A%7B%22time%22%3A1778646031484%2C%22noClick%22%3A1%7D%7D
.douyin.com    TRUE    /    FALSE    1810346913    SEARCH_RESULT_LIST_TYPE    %22single%22
.douyin.com    TRUE    /    FALSE    1817088124    volume_info    %7B%22isMute%22%3Afalse%2C%22isUserMute%22%3Afalse%2C%22volume%22%3A0.5%7D
www.douyin.com    FALSE    /    FALSE    1787711853    s_v_web_id    verify_mqvr266w_R2nYf7n7_HTCH_4hXo_8Rau_5mNUKEHOQi0q
www.douyin.com    FALSE    /    FALSE    1785070927    dy_swidth    1536
www.douyin.com    FALSE    /    FALSE    1785070927    dy_sheight    864
.douyin.com    TRUE    /    TRUE    1787711857    passport_csrf_token    d3d98a2b0f4e480609b68469f40e526d
.douyin.com    TRUE    /    FALSE    1787711857    passport_csrf_token_default    d3d98a2b0f4e480609b68469f40e526d
.douyin.com    TRUE    /    FALSE    1785070930    is_dash_user    1
.douyin.com    TRUE    /    TRUE    1813631863    sid_guard    0323087541144a1600c57672e7d59eab%7C1782527863%7C5184000%7CWed%2C+26-Aug-2026+02%3A37%3A43+GMT
.douyin.com    TRUE    /    TRUE    1787711863    session_tlb_tag    sttt%7C6%7CAyMIdUEUShYAxXZy59Weq__________jV8P1fWZel8b71z05-ykF755omC-hTFxf-w4ym64KUTE%3D
.douyin.com    TRUE    /    TRUE    1787711863    sid_ucp_v1    1.0.0-KDM4MmY3YzFkMTljMTAyNWQ1MjI4NDRhOWQxNGIxMzY3ZTgyMWEyZjEKIQi5hoDex63AAhD37vzRBhjvMSAMMJH4nsYGOAdA9AdIBBoCbGYiIDAzMjMwODc1NDExNDRhMTYwMGM1NzY3MmU3ZDU5ZWFi
.douyin.com    TRUE    /    TRUE    1787711863    ssid_ucp_v1    1.0.0-KDM4MmY3YzFkMTljMTAyNWQ1MjI4NDRhOWQxNGIxMzY3ZTgyMWEyZjEKIQi5hoDex63AAhD37vzRBhjvMSAMMJH4nsYGOAdA9AdIBBoCbGYiIDAzMjMwODc1NDExNDRhMTYwMGM1NzY3MmU3ZDU5ZWFi
.douyin.com    TRUE    /    FALSE    1817090956    my_rd    2
.douyin.com    TRUE    /    FALSE    1788165710    __security_mc_1_s_sdk_crypt_sdk    57f9abdf-49bd-848d
.douyin.com    TRUE    /    FALSE    1788165710    __security_mc_1_s_sdk_cert_key    e78cf606-4cba-9981
.douyin.com    TRUE    /    FALSE    1788165710    __security_mc_1_s_sdk_sign_data_key_web_protect    e57f223f-4bf6-bad7
.douyin.com    TRUE    /    FALSE    0    is_support_rtm_web_ts    1
www.douyin.com    FALSE    /    FALSE    0        douyin.com
www.douyin.com    FALSE    /    FALSE    0    device_web_cpu_core    16
www.douyin.com    FALSE    /    FALSE    0    device_web_memory_size    16
www.douyin.com    FALSE    /    FALSE    0    architecture    amd64
.iesdouyin.com    TRUE    /    FALSE    1814865058    ttwid    1%7CKiEZgPCIzN31IfcgwP9o0QV7NJCVaB3tyVuo83h7L_U%7C1783761057%7C250b85479232db74d644b5ddc65df1e9b7d22aa7b8f1851faa912ad51fffe0a2
.douyin.com    TRUE    /    FALSE    1784878011    FOLLOW_LIVE_POINT_INFO    %22MS4wLjABAAAA_5RG6IfnQ2TiW8LozM1Pa5gsmWTCrGod1C4_GchZ0ivQHZU67pqRtFknPy_mEp0_%2F1784307600000%2F0%2F1784273180957%2F0%22
www.douyin.com    FALSE    /    TRUE    0    csrf_session_id    01a13c3a155664fc4a023df8803ce7ac
.douyin.com    TRUE    /    FALSE    1784944654    download_guide    %223%2F20260718%2F0%22
.douyin.com    TRUE    /    FALSE    1784946243    playRecommendGuideTagCount    10
.douyin.com    TRUE    /    FALSE    1784946243    totalRecommendGuideTagCount    10
live.douyin.com    FALSE    /    TRUE    0    csrf_session_id    01a13c3a155664fc4a023df8803ce7ac
.douyin.com    TRUE    /    FALSE    1784983537    publish_badge_show_info    %220%2C0%2C0%2C1784378737942%22
.douyin.com    TRUE    /    FALSE    1785029014    strategyABtestKey    %221784424214.768%22
.douyin.com    TRUE    /    TRUE    1815570126    ttwid    1%7C7ijMQo98RXzYEJ9Jw78yJxdHCgkkcUkKeOdSUmd99EQ%7C1784424214%7C4bbbcfd5a5b3ce261580b9d8e7b494ef6f5c44fbae8cfc295063bd459713657e
.douyin.com    TRUE    /    FALSE    1816002132    __druidClientInfo    JTdCJTIyY2xpZW50V2lkdGglMjIlM0E0MzklMkMlMjJjbGllbnRIZWlnaHQlMjIlM0E2ODIlMkMlMjJ3aWR0aCUyMiUzQTQzOSUyQyUyMmhlaWdodCUyMiUzQTY4MiUyQyUyMmRldmljZVBpeGVsUmF0aW8lMjIlM0ExLjI1JTJDJTIydXNlckFnZW50JTIyJTNBJTIyTW96aWxsYSUyRjUuMCUyMChXaW5kb3dzJTIwTlQlMjAxMC4wJTNCJTIwV2luNjQlM0IlMjB4NjQpJTIwQXBwbGVXZWJLaXQlMkY1MzcuMzYlMjAoS0hUTUwlMkMlMjBsaWtlJTIwR2Vja28pJTIwQ2hyb21lJTJGMTUwLjAuMC4wJTIwU2FmYXJpJTJGNTM3LjM2JTIyJTdE
.douyin.com    TRUE    /    FALSE    1785070927    stream_recommend_feed_params    %22%7B%5C%22cookie_enabled%5C%22%3Atrue%2C%5C%22screen_width%5C%22%3A1536%2C%5C%22screen_height%5C%22%3A864%2C%5C%22cookie_enabled%5C%22%3Atrue%2C%5C%22userAgent%5C%22%3AMozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F150.0.0.0%20Safari%2F537.36%5C%22%7D%22"""

if __name__ == '__main__':
    is_valid, message = validate_cookies_content(cookies, 'douyin')
    print(f'Valid: {is_valid}')
    print(f'Message: {message}')