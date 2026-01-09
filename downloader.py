import streamlit as st
import yt_dlp
import os
import tempfile
import pandas as pd

# ==========================================
# 页面配置
# ==========================================
st.set_page_config(page_title="Elaina的合并下载器", page_icon="🦋", layout="wide")
st.title("🦋 Elaina's Advanced Merger Downloader")
st.markdown("---")
st.caption("提示：请确保服务器/本机已安装 FFmpeg，否则无法合并视频和音频。")

# 初始化状态
if 'video_info' not in st.session_state:
    st.session_state.video_info = None
if 'formats_df' not in st.session_state:
    st.session_state.formats_df = None
if 'cookie_path' not in st.session_state:
    st.session_state.cookie_path = None

# ==========================================
# Step 1 & 2: 链接与Cookie
# ==========================================
col1, col2 = st.columns([2, 1])

with col1:
    url = st.text_input("🔗 Step 1: 输入视频链接")

with col2:
    uploaded_cookie = st.file_uploader("🍪 Step 2: 上传 Cookie (可选)", type=['txt'])

# 处理 Cookie
cookie_temp_path = None
if uploaded_cookie is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='wb') as tmp:
        tmp.write(uploaded_cookie.getvalue())
        cookie_temp_path = tmp.name

# ==========================================
# Step 3: 解析格式
# ==========================================
if st.button("🔍 Step 3: 解析可用格式", type="primary"):
    if not url:
        st.error("请输入链接！")
    else:
        with st.spinner("正在解析魔导书..."):
            try:
                st.session_state.formats_df = None # 重置
                
                ydl_opts = {'quiet': True}
                if cookie_temp_path:
                    ydl_opts['cookiefile'] = cookie_temp_path

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    st.session_state.video_info = info
                    
                    formats_data = []
                    for f in info.get('formats', []):
                        fid = f.get('format_id')
                        # 过滤掉既没有视频也没有音频的无效格式
                        if f.get('vcodec') == 'none' and f.get('acodec') == 'none':
                            continue

                        # 整理显示数据
                        ext = f.get('ext')
                        res = f"{f.get('width')}x{f.get('height')}" if f.get('width') else "Audio Only"
                        
                        # 大小
                        fs = f.get('filesize') or f.get('filesize_approx')
                        size_str = f"{fs / 1024 / 1024:.2f} MB" if fs else "Unknown"
                        
                        # 备注信息
                        note = f.get('format_note', '')
                        vcodec = f.get('vcodec', 'none')
                        acodec = f.get('acodec', 'none')
                        
                        formats_data.append({
                            "ID": fid,
                            "类型": "🎬 视频" if vcodec != 'none' else "🎵 音频",
                            "格式": ext,
                            "分辨率": res,
                            "大小": size_str,
                            "编码": f"{vcodec} + {acodec}",
                            "备注": note
                        })
                    
                    # 存入 Pandas DataFrame
                    st.session_state.formats_df = pd.DataFrame(formats_data)
                    st.success(f"解析成功: {info.get('title')}")

            except Exception as e:
                st.error(f"解析失败: {e}")

# ==========================================
# Step 4: 表格交互选择
# ==========================================
if st.session_state.formats_df is not None:
    st.markdown("### 📋 Step 4: 在下方表格中直接点击选择 (支持多选)")
    st.info("💡 技巧：按住 Ctrl 或 Shift 可以选择多行。通常选择一个【视频流】和一个【音频流】进行合并。")

    # 使用 Streamlit 的 interactive dataframe
    # on_select="rerun" 表示一旦用户点击，脚本立刻重新运行以获取选中状态
    selection = st.dataframe(
        st.session_state.formats_df,
        use_container_width=True,
        on_select="rerun",  
        selection_mode="multi-row",
        hide_index=True
    )

    # 获取选中的行
    selected_rows = selection.selection.rows
    
    if selected_rows:
        # 从原始 DataFrame 中提取选中的 ID
        selected_ids = st.session_state.formats_df.iloc[selected_rows]["ID"].tolist()
        
        # 拼接成 yt-dlp 识别的格式字符串，例如 "137+140"
        format_string = "+".join(selected_ids)
        
        st.write("---")
        st.markdown(f"**已选择 Format ID:** `{format_string}`")
        
        # ==========================================
        # Step 5: 下载与合并
        # ==========================================
        if st.button(f"🚀 Step 5: 下载并合并 ({len(selected_ids)} 个流)"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        p = d.get('_percent_str', '0%').replace('%', '')
                        progress_bar.progress(min(float(p)/100, 1.0))
                        status_text.text(f"📥 下载中... {d.get('_percent_str')} | 速度: {d.get('_speed_str')}")
                    except:
                        pass
                elif d['status'] == 'finished':
                    status_text.text("⚙️ 下载完成，正在进行合并/转码处理 (FFmpeg)...")

            # 临时目录下载
            with tempfile.TemporaryDirectory() as tmpdir:
                ydl_opts = {
                    'format': format_string, # 这里传入拼接好的 ID
                    'outtmpl': f'{tmpdir}/%(title)s.%(ext)s',
                    'progress_hooks': [progress_hook],
                    'quiet': True,
                    # 如果需要合并，yt-dlp 默认会做，但需要 ffmpeg
                    'merge_output_format': 'mp4' # 强制合并为 mp4，防止合并成 mkv
                }
                if cookie_temp_path:
                    ydl_opts['cookiefile'] = cookie_temp_path

                try:
                    with st.spinner("正在施法 (下载 & 合并)..."):
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
                            
                            # 寻找最终生成的文件
                            # 因为合并后文件名可能会变（后缀变了），所以我们需要重新搜索
                            target_file = None
                            target_name = None
                            
                            # 获取目录里唯一的一个文件，或者最新的那个文件
                            files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir)]
                            if files:
                                target_file = max(files, key=os.path.getctime) # 找最新的
                                target_name = os.path.basename(target_file)
                            
                            if target_file and os.path.isfile(target_file):
                                # 读入内存
                                with open(target_file, "rb") as f:
                                    file_bytes = f.read()
                                
                                st.balloons()
                                st.success("🎉 搞定！")
                                st.download_button(
                                    label=f"💾 保存最终文件: {target_name}",
                                    data=file_bytes,
                                    file_name=target_name,
                                    mime="video/mp4" # 假设是mp4
                                )
                            else:
                                st.error("❌ 合并失败或未找到文件。请检查是否安装了 FFmpeg。")
                except Exception as e:
                    st.error(f"💥 发生错误: {e}")