import streamlit as st
from openai import OpenAI

# 페이지 설정
st.set_page_config(
    page_title="인사 서류 안내 챗봇",
    page_icon="📋",
    layout="centered",
)

st.title("📋 인사 서류 안내 챗봇")
st.caption("육아휴직 및 4대보험 피부양자 등록 관련 서류를 안내해드립니다.")

# OpenAI 클라이언트 초기화
@st.cache_resource
def get_openai_client():
    try:
        return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception:
        st.error("OPENAI_API_KEY가 secrets.toml에 설정되어 있지 않습니다.")
        st.stop()

client = get_openai_client()

# 자주 묻는 질문 정의
FAQ_QUESTIONS = [
    "4대보험 피부양자 등록을 하려면 어떤 서류를 제출해야 하나요?",
    "육아휴직 신청 시 제출해야 할 서류는 무엇인가요?",
    "육아휴직 1년 사용 후 6개월 연장 시 필요한 서류는 무엇인가요?",
    "육아휴직 급여를 얼마나 받을 수 있나요?",
    "출산휴가 후 육아휴직 바로 전환하려면 어떻게 하나요?",
]

# 시스템 프롬프트 정의
SYSTEM_PROMPT = """당신은 인사 서류 제출을 안내하는 친절한 HR 어시스턴트입니다.

주요 안내 사항:

**육아휴직 급여 신청을 위한 자녀 정보 제출 안내:**
- 공문으로 육아휴직 신청서 제출 시 자녀 주민등록번호 뒷자리가 기재된 가족관계증명서를 첨부해 주세요.
- 개인정보인 주민등록번호 공문 첨부가 우려되면 HR 담당자 이메일로 별도 송부해 주세요.
- 육아휴직 급여 지급을 위한 신청서 제출 시 자녀 주민등록번호 확인이 필요합니다(고용센터 필수 확인사항).
- 산전 휴직이면 자녀 주민번호를 알 수 없으므로 해당 없음.

**1년 육아휴직 사용 후 연장 신청 시 추가 증빙 안내:**
- 육아휴직 급여 대상기간은 1년이며, 부부가 모두 육아휴직을 사용하는 경우에 한해 1년 6개월까지 지급됩니다.
- 최초 1년 사용 후 추가 6개월 연장 시, 배우자가 동시에 3개월 이상 육아휴직을 사용했다는 증빙자료를 제출해 주세요. 없으면 제출 불필요.
- 배우자가 동시에 3개월 이상 육아휴직을 사용했다는 증빙자료:
  * 같은 자녀를 대상으로 부모가 모두 육아휴직을 각각 3개월 이상 사용한 경우의 부 또는 모
  * 증빙자료 예시: ▲육아휴직급여 지급 결정 통지서, ▲회사에서 공식적으로 발령한 휴직-복직 발령문(휴직 발령문만으로는 실제 휴직여부를 알 수 없으므로 복직 발령문도 함께 확인 필요)

**육아휴직 신청 시 기본 필요 서류:**
1. 육아휴직 신청서
2. 가족관계증명서 (주민등록번호 뒷자리 포함)

**출산휴가 후 육아휴직 바로 전환:**
- 통합신청서를 제출하면 됩니다.
- 통합신청서 작성 항목:
  1. 신청인의 성명, 생년월일 등 인적사항
  2. 육아휴직 대상인 영유아의 성명·생년월일
  3. 휴직개시예정일
  4. 육아휴직을 종료하려는 날
  5. 육아휴직 신청 연월일
  6. 출산전후휴가 또는 배우자출산휴가 개시예정일 및 종료일(통합신청시에만 기재)
- 자세한 내용은 링크 참고: https://www.moel.go.kr/news/notice/noticeView.do?bbs_seq=20250100161

**4대보험 피부양자 등록 시 필요 서류:**
- 피부양자 명의의 가족관계증명서 (주민등록번호 뒷자리 포함), 제출처는 회사 인사부서 담당자.

**추가 참고 사항:**
- 가족관계증명서는 주민센터 또는 정부24에서 발급 가능합니다.
- 주민등록번호 뒷자리가 포함되어야 합니다.
- 발급일로부터 3개월 이내 서류를 제출해야 합니다.

**육아휴직 급여 관련:**
- 육아휴직급여는 고용보험에 가입해 있는 피보험자가 받을 수 있습니다.
- 미리 알아보는 나의 육아휴직급여 지급액 모의계산: https://www.work24.go.kr/cm/c/f/1100/selecSimulate12.do?currentPageNo=1&recordCountPerPage=10&upprSystClId=SC00000245&systClId=SC00000251&systId=SI00000402&systCnntId=CI00001626
- 육아휴직급여에 관한 급여모의계산은 고용보험에 가입해 있는 피보험자가 육아휴직급여를 받게될 경우 받게 될 육아휴직급여를 계산해 볼 수 있습니다.

사용자의 질문에 따라 필요한 서류를 명확하고 친절하게 안내하세요. 단계별로 설명하고, 추가 궁금한 사항을 묻습니다."""

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "안녕하세요! 육아휴직이나 4대보험 피부양자 등록과 관련하여 필요한 서류를 안내해드립니다. 어떤 것이 궁금하신가요?",
        }
    ]

# 대화 히스토리 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# FAQ에서 추가된 질문이 있으면 AI 응답 생성
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_message = st.session_state.messages[-1]
    # 이미 응답이 생성되지 않은 경우에만 응답 생성
    needs_response = True
    if len(st.session_state.messages) >= 2:
        if st.session_state.messages[-2]["role"] == "assistant":
            # 이전 메시지가 assistant이면 새로운 user 메시지에 대한 응답 필요
            needs_response = True
    
    if needs_response and last_message["content"] in FAQ_QUESTIONS:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""

            try:
                messages_for_api = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.messages
                stream = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages_for_api,
                    stream=True,
                    temperature=0.7,
                    max_tokens=1000,
                )

                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        full_response += delta
                        placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)
            except Exception as e:
                full_response = f"오류가 발생했습니다: {e}"
                placeholder.error(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.rerun()

# 사용자 입력 처리
if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        try:
            messages_for_api = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.messages
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_api,
                stream=True,
                temperature=0.7,
                max_tokens=1000,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full_response += delta
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except Exception as e:
            full_response = f"오류가 발생했습니다: {e}"
            placeholder.error(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})

# 사이드바에 안내 정보 추가
with st.sidebar:
    st.header("📌 주요 안내")
    st.markdown("### 자주 묻는 질문")
    st.caption("질문을 클릭하면 챗봇이 답변해드립니다.")
    
    for i, question in enumerate(FAQ_QUESTIONS, 1):
        if st.button(f"Q{i}: {question}", key=f"faq_{i}", use_container_width=True):
            # FAQ 질문을 채팅에 추가
            st.session_state.messages.append({"role": "user", "content": question})
            st.rerun()

    st.divider()
    
    if st.button("대화 초기화", type="secondary", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "안녕하세요! 육아휴직이나 4대보험 피부양자 등록과 관련하여 필요한 서류를 안내해드립니다. 어떤 것이 궁금하신가요?",
            }
        ]
        st.rerun()
