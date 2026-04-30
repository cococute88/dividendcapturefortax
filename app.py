import streamlit as st
import yfinance as yf
import pandas as pd

# 웹사이트 넓게 쓰기
st.set_page_config(layout="wide")
st.title("🧸양도세치기 배당시뮬")

# 1. 왼쪽 사이드바(메뉴)에 설정칸 만들기
st.sidebar.header("⚙️ 전략 설정")
ticker_input = st.sidebar.text_input("티커 (예: SCHD, ARCC)", "ARCC")
ticker = ticker_input.upper() 

# 투자자금 입력칸 (기본값 10000)
invest_capital = st.sidebar.number_input("투자자금 (달러)", min_value=0, value=10000, step=1000)

# 매수가 기준과 매도허용기간
buy_type = st.sidebar.selectbox("매수가 기준", ["D-1 종가", "D-1 시가", "D-2 종가", "D-2 시가"])
sell_window = st.sidebar.number_input("매도허용기간 (N거래일)예:0,5", min_value=0, max_value=600, value=0)

# === 수정 3: 최근 5년 데이터만 보기 체크박스 추가 ===
recent_5y_only = st.sidebar.checkbox("최근 5년 데이터만 보기", value=False)

# 2. 버튼을 누르면 계산 시작!
if st.sidebar.button("백테스트 실행!"):
    with st.spinner(f'{ticker} 데이터를 야후에서 가져오는 중입니다...'):
        
        # 주가 및 배당금 데이터 한 번에 불러오기 (수정주가 미반영)
        data = yf.Ticker(ticker)
        df = data.history(period="max", auto_adjust=False)
        
        if df.empty:
            st.error(f"{ticker}의 주가 데이터를 찾을 수 없습니다. 티커명을 다시 확인해 주세요.")
        else:
            df.index = df.index.tz_localize(None).normalize()
            
            if 'Dividends' in df.columns:
                divs = df[df['Dividends'] > 0]['Dividends']
            else:
                divs = pd.Series(dtype=float)
            
            # === 수정 3: 최근 5년 데이터 필터링 로직 ===
            if recent_5y_only and not divs.empty:
                # 오늘 기준으로 5년 전 날짜 계산
                cutoff_date = pd.Timestamp.now().tz_localize(None).normalize() - pd.DateOffset(years=5)
                # 5년 전 날짜 이후의 배당금 데이터만 남기기
                divs = divs[divs.index >= cutoff_date]
            
            results = []
            
            # 3. 시뮬레이션 시작
            for ex_date, div_amount in divs.items():
                
                try:
                    idx = df.index.get_loc(ex_date)
                except KeyError:
                    continue 
                
                if idx < 2 or idx + sell_window >= len(df):
                    continue
                    
                # 사용자가 선택한 '매수가'
                if buy_type == "D-1 종가":
                    buy_price = df.iloc[idx-1]['Close']
                elif buy_type == "D-1 시가":
                    buy_price = df.iloc[idx-1]['Open']
                elif buy_type == "D-2 종가":
                    buy_price = df.iloc[idx-2]['Close']
                else: 
                    buy_price = df.iloc[idx-2]['Open']
                    
                # 세후 배당금
                after_tax_div = div_amount * 0.85
                
                # 손익분기점 (BEP)
                bep = buy_price - after_tax_div
                
                # 매도허용기간 동안의 장중 '최고가' 찾기
                window_data = df.iloc[idx : idx + sell_window + 1]
                max_high = window_data['High'].max()
                
                # 성공 판별 (최고가가 BEP 이상인가?)
                is_success = max_high >= bep
                
                # 수익률 계산 로직
                if is_success:
                    # 성공: 수익률은 (세후배당금 / 매수가) * 100 으로 고정
                    profit_pct = (after_tax_div / buy_price) * 100
                else:
                    # 실패: 매도기간 마지막 날 종가 매도 처리 + 세후 배당금 수령
                    sell_price = window_data.iloc[-1]['Close']
                    profit_pct = ((sell_price + after_tax_div - buy_price) / buy_price) * 100
                    
                results.append({
                    "배당락일": ex_date.strftime("%Y-%m-%d"),
                    "세후배당금": round(after_tax_div, 4),
                    "매수가": round(buy_price, 2),
                    "BEP": round(bep, 2),
                    "기간내 최고가": round(max_high, 2),
                    "성공여부": "성공" if is_success else "실패",
                    "수익률(%)": round(profit_pct, 2)
                })
                
            # 4. 화면에 결과 보여주기
            res_df = pd.DataFrame(results)
            
            if len(res_df) > 0:
                st.success(f"총 {len(res_df)}회의 과거 배당 이벤트 분석 완료!")
                
                # 백테스트 시작 및 종료 기간 표기
                start_date = res_df['배당락일'].iloc[0]
                end_date = res_df['배당락일'].iloc[-1]
                st.info(f"📅 백테스트 기간: {start_date} ~ {end_date}")
                
                # 핵심 지표 계산
                success_rate = (res_df['성공여부'] == '성공').mean() * 100
                avg_profit = res_df[res_df['성공여부'] == '성공']['수익률(%)'].mean()
                avg_loss = res_df[res_df['성공여부'] == '실패']['수익률(%)'].mean()
                
                # 1회 기대수익률 및 손익비 계산
                expected_return = res_df['수익률(%)'].mean()
                
                if pd.isna(avg_loss) or avg_loss == 0:
                    pl_ratio_str = "∞ (실패없음)"
                else:
                    pl_ratio = abs(avg_profit / avg_loss)
                    pl_ratio_str = f"{pl_ratio:.2f}"
                    
                # 절세예상액 계산 (수익률이 백분율이므로 100으로 나눔)
                if pd.notna(avg_profit):
                    tax_saving = (avg_profit / 100) * invest_capital * 0.22
                else:
                    tax_saving = 0
                
                # 멋진 카드 형태로 요약 보여주기 
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                col1.metric("전략 승률", f"{success_rate:.1f}%")
                col2.metric("성공 평균수익률", f"{avg_profit:.2f}%" if pd.notna(avg_profit) else "0%")
                col3.metric("실패 평균손실률", f"{avg_loss:.2f}%" if pd.notna(avg_loss) else "0%")
                col4.metric("손익비", pl_ratio_str)
                col5.metric("1회 기대수익률", f"{expected_return:.2f}%")
                col6.metric("1회 절세예상액", f"${tax_saving:.2f}")
                
                # 그래프 (점 형태의 산점도)
                st.write("### 📈 수익률 분포 그래프 (점)")
                st.scatter_chart(res_df, x='배당락일', y='수익률(%)', color='성공여부')

                # 상세 데이터 표
                st.write("### 📊 회차별 상세 백테스트 결과")
                st.dataframe(res_df)
                
            else:
                st.warning("분석할 수 있는 데이터가 없습니다. (해당 기간 내에 배당 내역이 없을 수 있습니다.)")