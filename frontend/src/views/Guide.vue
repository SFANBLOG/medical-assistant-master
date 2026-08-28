<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">就诊指南</h2>
    </div>

    <!-- 就诊流程 -->
    <el-card shadow="never" class="guide-card">
      <h3 class="card-title"><el-icon><Guide /></el-icon>就诊流程</h3>
      <el-steps :active="6" align-center class="flow-steps">
        <el-step title="预约挂号" description="线上/现场挂号" />
        <el-step title="分诊取号" description="到院分诊台" />
        <el-step title="候诊就诊" description="医生问诊" />
        <el-step title="检查检验" description="按医嘱检查" />
        <el-step title="缴费取药" description="结算与取药" />
        <el-step title="复诊随访" description="按约定复诊" />
      </el-steps>
    </el-card>

    <el-row :gutter="16" class="guide-row">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="guide-card">
          <h3 class="card-title"><el-icon><Calendar /></el-icon>挂号指南</h3>
          <ul class="guide-list">
            <li>线上挂号：通过「预约挂号」页面选择科室、医生与时间段，提前预约可减少排队时间。</li>
            <li>门诊时间：周一至周五 8:00 - 17:30，周六日上午 8:00 - 12:00（节假日另行通知）。</li>
            <li>初诊患者请携带身份证或医保卡办理就诊卡。</li>
            <li>复诊患者建议携带既往病历与检查报告。</li>
          </ul>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="guide-card">
          <h3 class="card-title"><el-icon><Document /></el-icon>就诊须知</h3>
          <ul class="guide-list">
            <li>就诊时请如实向医生描述病情、用药史与过敏史。</li>
            <li>请携带既往检查报告、影像资料，避免重复检查。</li>
            <li>高血压、糖尿病等慢性病复诊患者请携带近期的血压/血糖记录。</li>
            <li>对用药有疑问时，可在取药后咨询药师。</li>
          </ul>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="guide-row">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="guide-card">
          <h3 class="card-title"><el-icon><MagicStick /></el-icon>检查须知</h3>
          <ul class="guide-list">
            <li>空腹检查（如血糖、血脂、肝功能、腹部超声）：检查前 8-12 小时禁食禁水。</li>
            <li>胃镜、肠镜检查：需提前预约并按医嘱做肠道准备。</li>
            <li>心脏相关检查（心电图、动态心电图）：检查前避免剧烈运动与浓茶咖啡。</li>
            <li>检查时请携带申请单，放射检查请去除金属饰品。</li>
          </ul>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="guide-card">
          <h3 class="card-title"><el-icon><FirstAidKit /></el-icon>住院指南</h3>
          <ul class="guide-list">
            <li>凭医生开具的住院通知单到住院部办理入院手续。</li>
            <li>入院请携带：身份证、医保卡、生活用品与既往病历资料。</li>
            <li>住院期间请遵守探视时间，保持病房安静整洁。</li>
            <li>出院时到住院结算窗口办理费用结算，领取出院小结与带药。</li>
          </ul>
        </el-card>
      </el-col>
    </el-row>

    <!-- 常见问题 -->
    <el-card shadow="never" class="guide-card">
      <h3 class="card-title"><el-icon><QuestionFilled /></el-icon>常见问题</h3>
      <el-collapse>
        <el-collapse-item title="如何在线预约挂号？">
          登录系统后进入「预约挂号」页面，选择科室、日期与时间段，填写症状后提交即可。患者账号会自动绑定本人信息。
        </el-collapse-item>
        <el-collapse-item title="医保可以报销哪些费用？">
          医保报销范围、比例与定点政策有关，具体以当地医保政策为准。就诊结算时请出示医保卡。
        </el-collapse-item>
        <el-collapse-item title="检验检查报告如何获取？">
          可通过「健康档案」页面查看消费明细；详细检查报告请联系就诊科室或检验科查询。
        </el-collapse-item>
        <el-collapse-item title="智能咨询的结果可靠吗？">
          智能咨询基于医学知识库生成，仅供参考，不能替代医生面诊。如有不适请及时就医。
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-alert
      class="guide-alert"
      title="温馨提示：紧急情况请立即拨打 120 或前往就近医院急诊科就诊。"
      type="error"
      :closable="false"
      show-icon
    />
  </div>
</template>

<script setup lang="ts">
// 静态就诊指南页面
</script>

<style scoped>
.guide-card {
  margin-bottom: 16px;
  border-radius: 10px;
}

.guide-row {
  margin-top: 0;
}

.flow-steps {
  padding: 12px 0 24px;
}

.guide-list {
  margin: 0;
  padding-left: 18px;
  color: #606266;
  line-height: 2;
  font-size: 14px;
}

.guide-alert {
  margin-bottom: 16px;
}
</style>
