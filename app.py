import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# 1. Supabase 연동 설정
# ==========================================
SUPABASE_URL = "https://woiwopauuxrknraneduwi.supabase.co"
SUPABASE_KEY = "sb_publishable_dBSIztffefNGPnfOOFpv8Q_gLFhBDxz"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"클라우드 연결 오류: {e}")

# 클라우드 데이터 캐시 없이 실시간 조회 함수
def fetch_cloud_data():
    try:
        # st.cache_data를 사용하지 않고 매번 호출하여 실시간성 확보
        res = supabase.table("visitors").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df = df.drop_duplicates(subset=["visit_date", "center", "name", "phone"], keep="first")
            df["visit_date"] = df["visit_date"].astype(str).str.slice(0, 10).str.strip()
            # 비정상 날짜 텍스트 차단
            df = df[df["visit_date"].str.match(r"^\d{4}-\d{2}-\d{2}$") == True]
            return df
    except:
        pass
    return pd.DataFrame(columns=["visit_date", "center", "name", "phone", "id"])

# ==========================================
# 2. ⏳ [핵심 개선] 10초 주기 자동 화면 갱신 설정
# ==========================================
# 다른 사람이 업로드했을 때 내 화면의 필터와 표가 자동으로 업데이트되도록 유도
st.fragment(run_every=10)

# ==========================================
# 3. Streamlit 웹 UI 구성
# ==========================================
st.set_page_config(page_title="디동플 통합 데이터 시스템", layout="wide")

st.title("📊 디지털동행플라자 통합 데이터 관리 시스템")
st.caption("클라우드 기반 실시간 데이터 자동 동기화 대시보드입니다. (10초 간격 자동 갱신)")

# 사이드바 설정
sidebar = st.sidebar
sidebar.header("📁 데이터 업로드")
selected_center = sidebar.selectbox("업로드할 센터 선택", ["강동센터", "도봉센터", "동대문센터"])
uploaded_file = sidebar.file_uploader("방문자 엑셀 파일 선택", type=["xlsx", "xls"])

tab1, tab2 = st.tabs(["📈 실시간 대시보드", "🗑️ 내역 관리 및 삭제"])

# 최신 데이터 로드
real_df = fetch_cloud_data()

# --- TAB 1: 대시보드 ---
with tab1:
    if uploaded_file:
        try:
            input_df = pd.read_excel(uploaded_file, header=None)
            if input_df.shape[1] >= 5:
                input_df.columns = ["순번", "센터명", "성명", "전화번호", "방문시간"] + list(input_df.columns[5:])
            
            st.subheader("👀 업로드 미리보기")
            st.dataframe(input_df.head(10), use_container_width=True)
            
            if st.button("🚀 클라우드 창고로 전송", type="primary"):
                with st.spinner("창고에 저장 중..."):
                    success_count = 0
                    for _, row in input_df.iterrows():
                        v_name = str(row.get("성명")).strip()
                        if pd.isna(row.get("성명")) or v_name in ['nan', '이름', '성명', 'Unknown']: 
                            continue
                        
                        raw_date = row.get("방문시간", datetime.today().strftime('%Y-%m-%d'))
                        v_date = raw_date.strftime('%Y-%m-%d') if isinstance(raw_date, datetime) else str(raw_date)[:10].strip()
                        
                        v_phone = str(row.get("전화번호")).strip()
                        
                        supabase.table("visitors").insert({
                            "visit_date": v_date, 
                            "center": selected_center,
                            "name": v_name, 
                            "phone": v_phone
                        }).execute()
                        success_count += 1
                    st.success(f"🎉 {success_count}건 저장 완료!")
                    st.rerun()
        except Exception as e:
            st.error(f"오류: {e}")

    st.write("---")
    
    st.subheader("🗂️ 통합 엑셀 창고 데이터 실시간 조회")
    if not real_df.empty:
        st.write("🔍 **데이터 검색 필터**")
        f_col1, f_col2 = st.columns(2)
        
        with f_col1: 
            clean_dates = real_df["visit_date"].unique()
            date_list = ["전체보기"] + sorted([d for d in clean_dates if '-' in d], reverse=True)
            filter_date = st.selectbox("📆 방문 날짜 선택", date_list)
            
        with f_col2: 
            center_list = ["전체보기"] + sorted(list(real_df["center"].unique()))
            filter_center = st.selectbox("🏢 센터 선택", center_list)
        
        view_df = real_df.copy()
        if filter_date != "전체보기": 
            view_df = view_df[view_df["visit_date"] == filter_date]
        if filter_center != "전체보기": 
            view_df = view_df[view_df["center"] == filter_center]
        
        c1, c2 = st.columns(2)
        c1.metric("📊 조건별 조회 방문자", f"{len(view_df)} 명")
        c2.metric("👥 전체 누적 인원", f"{len(real_df)} 명")
        
        final_view = view_df[["visit_date", "center", "name", "phone"]].rename(columns={
            "visit_date": "방문일자",
            "center": "센터명",
            "name": "성명",
            "phone": "전화번호"
        })
        st.dataframe(final_view, use_container_width=True)
    else:
        st.warning("현재 창고에 보관된 데이터가 없습니다.")

# --- TAB 2: 삭제 관리 ---
with tab2:
    st.header("🗑️ 데이터 삭제 관리")
    if not real_df.empty:
        summary = real_df.groupby(["visit_date", "center"]).size().reset_index(name="count")
        for _, row in summary.sort_values("visit_date", ascending=False).iterrows():
            d, c, n = row["visit_date"], row["center"], row["count"]
            col_t, col_b = st.columns([4, 1])
            with col_t:
                st.info(f"📅 **[{d}] {c}** 등록 데이터 (총 {n}건 보관 중)")
            with col_b:
                if st.button("🗑️ 이 파일 삭제", key=f"del_{d}_{c}"):
                    supabase.table("visitors").delete().match({"visit_date": d, "center": c}).execute()
                    st.success("삭제 완료!")
                    st.rerun()
    else:
        st.write("데이터가 없습니다.")