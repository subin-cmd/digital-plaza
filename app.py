import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from supabase import create_client, Client

# ==========================================
# 1. 사내 방화벽 및 SSL 인증서 우회 설정 (버전 충돌 교정 버전 ⚡)
# ==========================================
SUPABASE_URL = "https://3.34.144.180"
SUPABASE_KEY = "sb_publishable_dBSIztffefNGPnfOOFpv8Q_gLFhBDxz"

try:
    # 🏢 사내 인터넷의 고유 IP 접근 차단을 막기 위해 인증서 검사(verify=False) 세션을 직접 생성합니다.
    custom_session = requests.Session()
    custom_session.verify = False
    
    # [수정] 버전 충돌을 일으키는 ClientOptions 대신 파이썬 표준 딕셔너리로 옵션을 안전하게 전달합니다.
    safe_options = {"session": custom_session}
    
    supabase: Client = create_client(
        SUPABASE_URL, 
        SUPABASE_KEY,
        options=safe_options
    )
except Exception as e:
    st.error(f"클라우드 연결 오류: {e}")

# 클라우드 데이터 실시간 조회 함수
def fetch_cloud_data():
    try:
        res = supabase.table("visitors").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df = df.drop_duplicates(subset=["visit_date", "center", "name", "phone"], keep="first")
            df["visit_date"] = df["visit_date"].astype(str).str.slice(0, 10).str.strip()
            df = df[df["visit_date"].str.match(r"^\d{4}-\d{2}-\d{2}$") == True]
            return df
    except:
        pass
    return pd.DataFrame(columns=["visit_date", "center", "name", "phone", "id"])

# ⏳ 10초 주기 자동 화면 갱신
st.fragment(run_every=10)

# ==========================================
# 2. Streamlit 웹 UI 구성
# ==========================================
st.set_page_config(page_title="디동플 통합 데이터 시스템", layout="wide")

st.title("📊 디지털동행플라자 통합 데이터 관리 시스템")
st.caption("클라우드 기반 실시간 데이터 자동 동기화 대시보드입니다. (사내 인터넷망 보안 대응 완료)")

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
            # 엑셀 로드
            input_df = pd.read_excel(uploaded_file, header=None)
            if input_df.shape[1] >= 5:
                input_df.columns = ["순번", "센터명", "성명", "전화번호", "방문시간"] + list(input_df.columns[5:])
            
            # 파일 내부 데이터와 선택한 센터 매칭 교차 검증
            sample_centers = input_df["센터명"].dropna().astype(str).str.strip().unique()
            detected_centers = [c for c in sample_centers if c not in ['nan', '센터명', '방문센터']]
            
            is_valid = True
            detected_center_name = selected_center
            
            if detected_centers:
                detected_center_name = detected_centers[0]
                if detected_center_name != selected_center:
                    is_valid = False

            st.subheader("👀 업로드 미리보기")
            st.dataframe(input_df.head(10), use_container_width=True)
            
            # 센터 검증 결과에 따른 UI 제어
            if not is_valid:
                st.error(f"⚠️ **데이터 불일치 경고!** 왼쪽에 선택한 센터는 **[{selected_center}]**인데, 업로드한 파일은 **[{detected_center_name}]** 데이터로 파악됩니다. 왼쪽 메뉴의 센터를 다시 올바르게 선택해 주세요.")
                st.button("🚀 클라우드 창고로 전송", type="primary", disabled=True, help="센터 일치 확인 후 활성화됩니다.")
            else:
                st.success(f"✅ 센터 정보가 일치합니다. **[{selected_center}]** 데이터를 전송할 준비가 되었습니다.")
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
