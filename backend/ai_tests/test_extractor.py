import unittest
from types import SimpleNamespace
from pathlib import Path
from user_extraction.schema import ExtractionResult, Place, empty_result
from user_extraction.normalization import normalize_result,normalize_gu,SEOUL_GU
from user_extraction.demo_rules import demo_extract
from user_extraction.extractor import extract_user_info
from evaluate import get_prediction

class NormalizationTests(unittest.TestCase):
 def test_seoul_has_25(self):self.assertEqual(len(SEOUL_GU),25)
 def test_city_alias(self):
  self.assertEqual(normalize_gu('마포'), '마포구')
  self.assertEqual(normalize_gu('이태원'), '용산구')
  self.assertIsNone(normalize_gu('신촌'))
  self.assertIsNone(normalize_gu('없는동'))
 def test_null_region_no_filter(self):
  r=normalize_result('카페 창업',empty_result())
  self.assertIsNone(r.검색정보.검색지역)
  self.assertIsNone(r.검색정보.검색시도)
 def test_prestart_priority(self):
  r=empty_result()
  r.추가추출값.창업단계_언급='예비'
  r.사용자프로필.거주지=Place(시도='서울',권역=None,시군구='성북구')
  r.사용자프로필.창업예정지=Place(시도='서울',권역=None,시군구='마포')
  r=normalize_result('성북구 살고 마포에서 창업',r)
  self.assertEqual(r.검색정보.검색지역,'마포구')
  self.assertEqual(r.검색정보.검색시도,'서울특별시')
 def test_prestart_residence_fallback(self):
  r=empty_result();r.추가추출값.창업단계_언급='예비'
  r.사용자프로필.거주지=Place(시도='서울',권역=None,시군구='성북구')
  self.assertEqual(normalize_result('성북구 살아요',r).검색정보.검색지역,'성북구')
 def test_operating_business_location(self):
  r=empty_result();r.추가추출값.창업단계_언급='개업'
  r.사용자프로필.거주지=Place(시도='서울',권역=None,시군구='강남구')
  r.사용자프로필.사업장소재지=Place(시도='서울',권역=None,시군구='이태원')
  self.assertEqual(normalize_result('강남 거주 이태원 운영',r).검색정보.검색지역,'용산구')
 def test_no_stage_cannot_guess_location_role(self):
  r=empty_result();r.사용자프로필.거주지=Place(시도='서울',권역=None,시군구='성북구')
  self.assertIsNone(normalize_result('성북구에 살아요',r).검색정보.검색지역)
 def test_dedup_categories(self):
  r=empty_result();r.검색정보.필요지원=['미지정','자금','자금']
  self.assertEqual(normalize_result('대출 필요',r).검색정보.필요지원,['자금'])
 def test_max_two_ksic(self):
  r=empty_result();r.사용자프로필.업종=['I','G','C']
  self.assertEqual(normalize_result('카페',r).사용자프로필.업종,['I','G'])
 def test_unknown_birth_not_fabricated(self):
  r=empty_result();r.추가추출값.나이_언급=29
  r=normalize_result('29살',r)
  self.assertIsNone(r.사용자프로필.생년월일)
 def test_invalid_iso_date(self):
  r=empty_result().model_dump(mode='json');r['사용자프로필']['생년월일']='2026-02-30'
  with self.assertRaises(ValueError):ExtractionResult.model_validate(r)

class DemoTests(unittest.TestCase):
 def test_example_q01(self):
  r=demo_extract('29살이고 마포구에서 디저트 카페를 준비하는 예비창업자예요. 오픈하면 라이브커머스로도 판매해보고 싶어요.')
  self.assertEqual(r['검색정보']['검색지역'],'마포구')
  self.assertEqual(r['검색정보']['필요지원'],['홍보·판매'])
  self.assertEqual(r['추가추출값']['나이_언급'],29)
  self.assertIsNone(r['사용자프로필']['생년월일'])
 def test_unspecified_support(self):
  self.assertEqual(demo_extract('카페 창업하고 싶어요.')['검색정보']['필요지원'],['미지정'])
 def test_mentions_neighborhood_only(self):
  r=demo_extract('이태원에서 음식점을 운영 중이에요. 자금 지원이 필요해요.')
  self.assertEqual(r['검색정보']['검색지역'],'용산구')
 def test_registration_not_form(self):
  r=demo_extract('마포구에서 독립서점을 열려고요. 아직 사업자등록 전입니다.')
  self.assertIsNone(r['사용자프로필']['기업형태'])
  self.assertIsNone(r['사용자프로필']['사업자이력'])  # 등록 전 != 과거 등록이력 없음
 def test_duration_converts_months(self):
  r=demo_extract('미용실을 개인사업자로 운영한 지 5년 됐어요.')
  self.assertEqual(r['추가추출값']['업력_개월'],60)
  self.assertIsNone(r['사용자프로필']['창업일'])
 def test_keywords_no_support(self):
  r=demo_extract('누가 옆에서 봐주면 좋겠어요. 카페를 준비 중이에요.')
  self.assertIn('멘토링',r['검색정보']['필요지원키워드'])
 def test_q28_situation(self):
  r=demo_extract('반찬가게를 연 지 1년 됐어요. 손님이 줄어서 가게 말고 다른 방법으로도 팔아보고 싶어요.')
  self.assertIn('매출 감소',r['검색정보']['상황키워드'])
 def test_output_can_validate(self):
  d=demo_extract('카페 창업하고 싶어요.')
  self.assertEqual(ExtractionResult.model_validate(d).model_dump(mode='json'),d)

class SchemaDoubleCheckTests(unittest.TestCase):
 def test_schema_v04_section4_field_names(self):
  # Exact field names from the supplied v0.4 Schema section 4.
  from user_extraction.schema import UserProfile
  expected = {
   '사용자ID','생년월일','성별','거주지','창업예정지','사업장소재지','창업일',
   '기업형태','상시근로자수','연매출_원','보유요건','업종','사업자이력',
   '최근폐업일','폐업업종','특수자격','제외해당','프랜차이즈',
  }
  self.assertEqual(set(UserProfile.model_fields), expected)
 def test_corporation_future_not_existing(self):
  r=demo_extract('법인을 만들고 싶어요.')
  p=r['사용자프로필']; e=r['추가추출값']
  self.assertIsNone(p['기업형태'])
  self.assertIsNone(p['사업자이력'])
  self.assertIsNone(e['현재사업자등록상태'])
 def test_unregistered_without_history_not_no_history(self):
  r=demo_extract('사업자등록은 아직 안 했어요.')
  self.assertIsNone(r['사용자프로필']['사업자이력'])
  self.assertEqual(r['추가추출값']['현재사업자등록상태'],'미등록')
  self.assertIsNone(r['추가추출값']['창업단계_언급'])
 def test_closed_history_precedes_unregistered(self):
  r=demo_extract('사업자등록 전인데 예전에 폐업한 적이 있어요.')
  self.assertEqual(r['사용자프로필']['사업자이력'],'폐업')
  self.assertEqual(r['추가추출값']['현재사업자등록상태'],'미등록')
 def test_explicit_no_registration_history(self):
  r=demo_extract('사업자등록을 한 적이 없어요.')
  self.assertEqual(r['사용자프로필']['사업자이력'],'없음')
 def test_q02_inferred_stage_is_not_registration(self):
  r=demo_extract('크라우드펀딩으로 창업 자금을 모아보고 싶어요.')
  self.assertEqual(r['추가추출값']['창업단계_언급'],'예비')
  self.assertIsNone(r['사용자프로필']['사업자이력'])
  self.assertEqual(r['검색정보']['필요지원'],['자금'])
 def test_hypothetical_operation_not_opened(self):
  r=demo_extract('성북구에서 청년 창업팀으로 소품 가게를 운영해보고 싶은데 매장이 필요해요.')
  self.assertEqual(r['추가추출값']['창업단계_언급'],'예비')
 def test_existing_corporation(self):
  r=demo_extract('법인 세운 지 6개월 된 스타트업 대표예요.')
  self.assertEqual(r['사용자프로필']['기업형태'],'법인')
  self.assertEqual(r['사용자프로필']['사업자이력'],'현재보유')
 def test_unknown_values_remain_null(self):
  r=demo_extract('카페 창업하고 싶어요.')
  self.assertIsNone(r['사용자프로필']['생년월일'])
  self.assertIsNone(r['사용자프로필']['사업자이력'])
  self.assertIsNone(r['검색정보']['검색지역'])
 def test_age_does_not_fabricate_birthdate(self):
  r=demo_extract('29살 예비창업자예요.')
  self.assertIsNone(r['사용자프로필']['생년월일'])
  self.assertEqual(r['추가추출값']['나이_언급'],29)

class LLMInterfaceTests(unittest.TestCase):
 def test_inject_mock_api_client(self):
  sample=empty_result();sample.추가추출값.창업단계_언급='예비'
  sample.사용자프로필.창업예정지=Place(시도='서울',권역=None,시군구='마포구')
  class MockResponses:
   def parse(self,**kwargs):
    self.args=kwargs
    return SimpleNamespace(output_parsed=sample)
  r=MockResponses()
  obj=extract_user_info('마포구에서 창업할 거예요.',user_id='U01',client=SimpleNamespace(responses=r))
  self.assertEqual(obj['사용자프로필']['사용자ID'],'U01')
  self.assertEqual(obj['검색정보']['검색지역'],'마포구')
  self.assertIs(r.args['text_format'],ExtractionResult)
  self.assertIs(r.args['store'],False)
 def test_no_output_rejected(self):
  class MockResponses:
   def parse(self,**kwargs):return SimpleNamespace(output_parsed=None)
  with self.assertRaises(RuntimeError):extract_user_info('카페',client=SimpleNamespace(responses=MockResponses()))
 def test_empty_input_rejected(self):
  with self.assertRaises(ValueError):extract_user_info('   ')

if __name__=='__main__':unittest.main()
