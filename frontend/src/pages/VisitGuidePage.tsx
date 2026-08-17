import { Card, Col, Row, Steps, Typography } from 'antd'
import {
  IdcardOutlined,
  SearchOutlined,
  MedicineBoxOutlined,
  CheckCircleOutlined,
  InboxOutlined,
} from '@ant-design/icons'

const { Title, Paragraph, Text } = Typography

export default function VisitGuidePage() {
  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>
        就诊指南
      </Title>
      <Card title="门诊就诊流程" style={{ marginBottom: 16 }}>
        <Steps
          direction="vertical"
          size="small"
          items={[
            {
              title: '预约挂号',
              icon: <IdcardOutlined />,
              description: '通过本系统“预约挂号”或医院自助机、公众号提前挂号，选择科室与就诊时段。',
            },
            {
              title: '候诊报到',
              icon: <InboxOutlined />,
              description: '按预约时间到相应科室分诊台报到，持身份证/就诊卡，按叫号顺序就诊。',
            },
            {
              title: '医师接诊',
              icon: <SearchOutlined />,
              description: '如实向医生描述病情、既往病史与用药情况，配合体格检查，必要时开立检查检验。',
            },
            {
              title: '检查检验',
              icon: <MedicineBoxOutlined />,
              description: '凭检查申请单缴费后到相应科室检查，领取报告后再请医生解读。',
            },
            {
              title: '取药离院 / 办理住院',
              icon: <CheckCircleOutlined />,
              description: '按处方取药或按医嘱办理住院；离院后遵医嘱复诊与随访。',
            },
          ]}
        />
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card title="门诊时间">
            <Paragraph>
              普通门诊：周一至周日 08:00 - 12:00，14:00 - 17:30
              <br />
              急诊：24 小时开放（危急重症请直接前往急诊科）
              <br />
              法定节假日门诊安排以医院公告为准
            </Paragraph>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="就诊准备">
            <Paragraph>
              · 携带本人身份证/医保卡
              <br />· 就诊记录、体检报告、近期用药清单
              <br />· 儿童就诊请家长陪同并携带预防接种记录
            </Paragraph>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="温馨提示">
            <Paragraph>
              · 挂号实名制，请勿转借他人
              <br />· 候诊时请留意叫号屏幕
              <br />· 危急重症、外伤出血请直接到急诊科
              <br />· 本平台内容仅用于科普，具体诊疗以医生意见为准
            </Paragraph>
          </Card>
        </Col>
      </Row>
      <Text type="secondary">本指南为通用就诊流程介绍，具体以医院实际安排为准。</Text>
    </div>
  )
}
