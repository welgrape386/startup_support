"""Schema v0.4 user profile + search-only fields. Not an announcement schema."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator

KSIC = Literal['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U']
Category = Literal['자금','교육·컨설팅','공간·시설','홍보·판매','인력','기술개발','해외진출','제도·인증','기타','미지정']

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Place(StrictModel):
    시도: str | None = None
    권역: str | None = None
    시군구: str | None = None

class UserProfile(StrictModel):
    # Source: supplied "Schema" HTML section 4 (user, NOT announcement eligibility)
    사용자ID: str | None = None
    생년월일: str | None = None
    성별: Literal['여성','남성'] | None = None
    거주지: Place | None = None
    창업예정지: Place | None = None
    사업장소재지: Place | None = None
    창업일: str | None = None
    기업형태: Literal['개인사업자','법인'] | None = None
    상시근로자수: int | None = None
    연매출_원: int | None = None
    보유요건: list[str]
    업종: list[KSIC]
    사업자이력: Literal['없음','폐업','현재보유'] | None = None
    최근폐업일: str | None = None
    폐업업종: KSIC | None = None
    특수자격: list[str]
    제외해당: list[str]
    프랜차이즈: Literal['아님','가맹점','직영점','가맹본부'] | None = None

    @field_validator('생년월일','창업일','최근폐업일')
    @classmethod
    def check_date(cls, v: str | None) -> str | None:
        if v is None: return None
        from datetime import date
        try:
            if len(v)!=10 or date.fromisoformat(v).isoformat()!=v:
                raise ValueError('date must be YYYY-MM-DD')
        except ValueError as exc:
            raise ValueError('date must be a real YYYY-MM-DD date') from exc
        return v

class SearchInfo(StrictModel):
    검색지역: str | None = None  # Seoul full borough or other unambiguous sigungu; null -> no district filtering
    검색시도: str | None = None
    필요지원: list[Category]   # ['미지정'] is the sentinel, never mixed with a real category
    필요지원키워드: list[str]
    상황키워드: list[str]
    업종원문표현: str | None = None

class ExtraValues(StrictModel):
    # Do not fabricate birth/opening dates from an age or opening duration.
    나이_언급: int | None = None
    창업단계_언급: Literal['예비','개업'] | None = None
    업력_개월: int | None = None
    현재사업자등록상태: Literal['등록','미등록'] | None = None
    기업규모_표현: str | None = None
    자금_언급_원: int | None = None   # mere mentioned amount, NOT necessarily funding gap

class ExtractionResult(StrictModel):
    사용자프로필: UserProfile
    검색정보: SearchInfo
    추가추출값: ExtraValues


def empty_result() -> ExtractionResult:
    return ExtractionResult(
        사용자프로필=UserProfile(보유요건=[], 업종=[], 특수자격=[], 제외해당=[]),
        검색정보=SearchInfo(필요지원=['미지정'], 필요지원키워드=[], 상황키워드=[]),
        추가추출값=ExtraValues(),
    )
