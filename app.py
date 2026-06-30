import streamlit as st
import pandas as pd
from datetime import datetime
import os

# ==========================================
# 1. 로컬 엑셀 파일 저장 경로 및 데이터 처리
# ==========================================
DB_FILE = "통합관리_데이터베이스.xlsx"

def fetch_local_data():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_excel(DB_FILE)
            df = df.drop_duplicates(subset=["visit_date", "center", "name", "phone"], keep="first")
            return df
        except Exception:
            return pd.DataFrame(columns=["visit_date", "center", "name", "phone"])
    return pd.DataFrame(columns=["visit_date", "center", "name", "phone"])

real_df = fetch_local_data()

# 데이터 타입 강제 정제 및 텍스트 찌꺼기 차단
if not real_df.empty:
    real_df["visit_date"] = real_df["visit_date"].astype(str).str.slice(0, 10).str.strip()
    real_df = real_df[real_df["visit_date"].str.match(r"^\d{4}-\d{2}-\d{2}$") == True]

# ==========================================
# 2. Streamlit 웹 UI 구성
# ==========================================
st.set_page_config(page_title="디동플 일일데이터 자동화 시스템 (로컬 버전)", layout="wide")

st.title("📂 디지털동행플라자 통합 데이터 관리 시스템")
st.caption("사내 보안망 독립형 로컬 엑셀 통합 누적 관리 시스템입니다.")

# 사이드바 설정
sidebar = st.sidebar
sidebar.header("📁 데이터 업로드 및 설정")
selected_center = sidebar.selectbox("업로드할 센터 선택", ["강동센터", "도봉센터", "동대문센터"])
uploaded_file = sidebar.file_uploader("센터별 방문자 엑셀 파일 선택", type=["xlsx", "xls"])

# --- 메인 화면 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📈 대시보드 및 업로드", "🗑️ 업로드 내역 관리 (삭제)", "⚙️ 시스템 정보"])

# --- TAB 1: 대시보드 및 업로드 ---
with tab1:
    st.header("📈 실시간 통합 데이터 대시보드")
    
    if uploaded_file is not None:
        st.success(f"📂 파일이 성공적으로 감지되었습니다: {uploaded_file.name}")
        try:
            input_df = pd.read_excel(uploaded_file, header=None)
            if input_df.shape[1] >= 5:
                input_df.columns = ["순번", "센터명", "성명", "전화번호", "방문시간"] + list(input_df.columns[5:])
            
            st.subheader("👀 업로드한 엑셀 파일 미리보기")
            st.dataframe(input_df, use_container_width=True)
            
            if st.button("🚀 데이터 분석 및 통합 엑셀 누적 저장", type="primary"):
                with st.spinner("데이터를 분석하여 창고 파일에 안전하게 저장 중..."):
                    new_rows = []
                    
                    for _, row in input_df.iterrows():
                        v_name = str(row.get("성명")).strip()
                        if pd.isna(row.get("성명")) or v_name in ['nan', '이름', '성명', 'Unknown']:
                            continue
                            
                        raw_date = row.get("방문시간", datetime.today().strftime('%Y-%m-%d'))
                        if isinstance(raw_date, datetime):
                            v_date = raw_date.strftime('%Y-%m-%d')
                        else:
                            v_date = str(raw_date)[:10].strip()
                        
                        import re
                        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v_date):
                            continue
                            
                        v_phone = str(row.get("전화번호")).strip()
                        
                        new_rows.append({
                            "visit_date": v_date,
                            "center": selected_center,
                            "name": v_name,
                            "phone": v_phone
                        })
                    
                    if new_rows:
                        new_df = pd.DataFrame(new_rows)
                        combined_df = pd.concat([real_df, new_df], ignore_index=True)
                        combined_df = combined_df.drop_duplicates(subset=["visit_date", "center", "name", "phone"], keep="first")
                        combined_df.to_excel(DB_FILE, index=False)
                        st.success(f"🎉 성공적으로 중복을 제외한 {len(new_df)}건의 데이터가 누적 저장되었습니다!")
                        st.rerun()
                    else:
                        st.warning("업로드할 유효한 새 데이터가 없습니다.")
                    
        except Exception as e:
            st.error(f"오류가 발생했습니다. 에러내용: {e}")
            
    else:
        st.info("💡 왼쪽 메뉴바에서 엑셀 파일을 업로드하면 누적 저장 버튼이 나타납니다.")

    st.write("---")
    st.subheader("🗂️ 통합 엑셀 창고 데이터 실시간 조회")
    
    if not real_df.empty:
        st.write("🔍 **데이터 검색 필터**")
        filter_col1, filter_col2 = st.columns(2)
        
        with filter_col1:
            clean_dates = real_df["visit_date"].unique()
            date_list = ["전체보기"] + sorted([d for d in clean_dates if '-' in d], reverse=True)
            filter_date = st.selectbox("📆 방문 날짜 선택", date_list)
            
        with filter_col2:
            center_list = ["전체보기"] + sorted(list(real_df["center"].unique()))
            filter_center = st.selectbox("🏢 센터 선택", center_list)
            
        filtered_df = real_df.copy()
        if filter_date != "전체보기":
            filtered_df = filtered_df[filtered_df["visit_date"] == filter_date]
        if filter_center != "전체보기":
            filtered_df = filtered_df[filtered_df["center"] == filter_center]
            
        col1, col2 = st.columns(2)
        col1.metric("📊 조건별 조회 방문자", f"{len(filtered_df)} 명")
        col2.metric("👥 전체 누적 인원", f"{len(real_df)} 명")
        
        view_df = filtered_df.rename(columns={
            "visit_date": "방문일자",
            "center": "센터명",
            "name": "성명",
            "phone": "전화번호"
        })
        st.dataframe(view_df, use_container_width=True)
    else:
        st.warning("현재 누적된 데이터가 없습니다. 첫 엑셀 파일을 업로드해서 데이터를 쌓아보세요!")

# --- 🌟 TAB 2: 업로드 내역 관리 및 선택 삭제 기능 🌟 ---
with tab2:
    st.header("🗑️ 저장된 센터별 일일 파일 내역 관리")
    st.write("누적 창고 파일에 저장된 데이터의 요약 목록입니다. 잘못 업로드한 특정 날짜의 센터 데이터를 골라 삭제할 수 있습니다.")
    
    if not real_df.empty:
        # 날짜와 센터별로 묶어서 몇 건씩 들어있는지 목록화
        summary_df = real_df.groupby(["visit_date", "center"]).size().reset_index(name="데이터 건수")
        summary_df = summary_df.sort_values(by=["visit_date", "center"], ascending=[False, True])
        
        st.write("---")
        # 깔끔하게 한 줄씩 목록을 띄우고 삭제 버튼 매칭
        for idx, row in summary_df.iterrows():
            v_date = row["visit_date"]
            v_center = row["center"]
            v_count = row["데이터 건수"]
            
            # 사용자 눈에 직관적으로 보이도록 포맷 변경 (예: [2026-06-26] 강동센터 입장내역 - 192명)
            col_text, col_btn = st.columns([4, 1])
            
            with col_text:
                st.info(f"📅 **[{v_date}] {v_center}** 등록 데이터 (총 {v_count}건 보관 중)")
                
            with col_btn:
                # 각 행마다 고유한 삭제 버튼 생성
                if st.button(f"🗑️ 이 파일 삭제", key=f"del_{v_date}_{v_center}"):
                    # 선택한 날짜와 센터 조건만 빼고 나머지만 남기기 (필터링 삭제)
                    updated_df = real_df[~((real_df["visit_date"] == v_date) & (real_df["center"] == v_center))]
                    
                    # 엑셀 파일에 다시 덮어쓰기 저장
                    updated_df.to_excel(DB_FILE, index=False)
                    st.success(f"💥 [{v_date}] {v_center} 데이터가 성공적으로 삭제되었습니다!")
                    st.rerun()
    else:
        st.warning("현재 창고에 보관된 데이터 내역이 없어 삭제할 수 없습니다.")

# --- TAB 3: 시스템 정보 ---
with tab3:
    st.header("⚙️ 시스템 정보")
    st.info(f"본 프로그램은 인터넷 연결 없이 작동합니다. 모든 데이터는 프로그램과 같은 폴더 안의 [{DB_FILE}] 파일에 누적 저장됩니다.")