<template>
  <div>
    <h4 class="page-title">就诊指南</h4>
    <el-card style="margin-bottom: 16px">
      <template #header>门诊就诊流程</template>
      <el-steps direction="vertical" :active="5" style="max-width: 640px">
        <el-step title="预约挂号" description="通过本系统“预约挂号”或医院自助机、公众号提前挂号，选择科室与就诊时段。" />
        <el-step title="候诊报到" description="按预约时间到相应科室分诊台报到，持身份证/就诊卡，按叫号顺序就诊。" />
        <el-step title="医师接诊" description="如实向医生描述病情、既往病史与用药情况，配合体格检查，必要时开立检查检验。" />
        <el-step title="检查检验" description="凭检查申请单缴费后到相应科室检查，领取报告后再请医生解读。" />
        <el-step title="取药离院 / 办理住院" description="按处方取药或按医嘱办理住院；离院后遵医嘱复诊与随访。" />
      </el-steps>
    </el-card>
    <el-row :gutter="16">
      <el-col :xs="24" :md="8">
        <el-card>
          <template #header>门诊时间</template>
          <p>
            普通门诊：周一至周日 08:00 - 12:00，14:00 - 17:30<br />
            急诊：24 小时开放（危急重症请直接前往急诊科）<br />
            法定节假日门诊安排以医院公告为准
          </p>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card>
          <template #header>就诊准备</template>
          <p>
            · 携带本人身份证/医保卡<br />
            · 就诊记录、体检报告、近期用药清单<br />
            · 儿童就诊请家长陪同并携带预防接种记录
          </p>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card>
          <template #header>温馨提示</template>
          <p>
            · 挂号实名制，请勿转借他人<br />
            · 候诊时请留意叫号屏幕<br />
            · 危急重症、外伤出血请直接到急诊科<br />
            · 本平台内容仅用于科普，具体诊疗以医生意见为准
          </p>
        </el-card>
      </el-col>
    </el-row>
    <p style="color: #999">本指南为通用就诊流程介绍，具体以医院实际安排为准。</p>
  </div>
</template>
