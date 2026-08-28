<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">健康资讯</h2>
      <div class="spacer"></div>
      <el-input
        v-model="keyword"
        placeholder="搜索健康资讯"
        clearable
        :prefix-icon="'Search'"
        style="width: 240px"
      />
    </div>

    <el-row :gutter="16">
      <el-col
        v-for="article in filteredArticles"
        :key="article.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
        class="article-col"
      >
        <el-card shadow="hover" class="article-card" @click="openArticle(article)">
          <div class="article-cat" :style="{ background: article.color }">
            {{ article.category }}
          </div>
          <h3 class="article-title">{{ article.title }}</h3>
          <p class="article-summary">{{ article.summary }}</p>
          <div class="article-footer">
            <span class="article-date">{{ article.date }}</span>
            <span class="article-read">阅读全文 →</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!filteredArticles.length" description="没有匹配的资讯" />

    <!-- 文章详情 -->
    <el-dialog v-model="dialogVisible" :title="current?.title" width="680px">
      <div class="article-meta">
        <el-tag size="small" effect="plain">{{ current?.category }}</el-tag>
        <span>{{ current?.date }}</span>
      </div>
      <div class="article-body">
        <p v-for="(p, i) in current?.content" :key="i" class="article-para">
          {{ p }}
        </p>
        <div class="disclaimer">* 本文内容仅供健康科普参考，不能替代专业医疗诊断与治疗建议。</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Article {
  id: number
  category: string
  color: string
  title: string
  summary: string
  date: string
  content: string[]
}

const articles: Article[] = [
  {
    id: 1,
    category: '慢性病管理',
    color: '#409eff',
    title: '高血压患者的日常自我管理',
    summary: '定期监测血压、低盐饮食、规律服药，是控制高血压的三大基石。',
    date: '2026-08-20',
    content: [
      '高血压被称为"沉默的杀手"，多数患者早期无明显症状，但长期血压升高会显著增加心脑血管事件风险。',
      '自我管理要点：1) 每日固定时间测量血压并记录，家庭血压目标建议低于 135/85mmHg；2) 限制钠盐摄入，每日食盐量不超过 5 克，减少腌制食品与加工食品；3) 遵医嘱规律服药，切勿自行停药或减量；4) 保持规律运动，如每周 5 次、每次 30 分钟的中等强度有氧运动；5) 控制体重，戒烟限酒，保证充足睡眠。',
      '如果出现剧烈头痛、视物模糊、胸闷胸痛等不适，应立即就医。',
    ],
  },
  {
    id: 2,
    category: '营养膳食',
    color: '#67c23a',
    title: '糖尿病患者的饮食与运动建议',
    summary: '管住嘴、迈开腿，科学饮食与规律运动是控糖的核心。',
    date: '2026-08-18',
    content: [
      '饮食管理是糖尿病治疗的基石。建议少食多餐，定时定量，主食粗细搭配，多摄入蔬菜与优质蛋白。',
      '水果并非完全禁忌，可在血糖控制稳定时，选择升糖指数低的水果（如苹果、梨、柚子），在两餐之间少量食用。',
      '运动方面，建议餐后 30 分钟进行快走、慢跑、游泳等有氧运动，每周累计 150 分钟以上，同时进行适度抗阻训练。',
      '注意监测血糖，携带糖果或含糖饮料以预防低血糖。',
    ],
  },
  {
    id: 3,
    category: '传染病预防',
    color: '#f56c6c',
    title: '秋冬季流感预防指南',
    summary: '接种疫苗、勤洗手、戴口罩，有效降低流感感染风险。',
    date: '2026-08-15',
    content: [
      '流行性感冒（流感）由流感病毒引起，传播快、波及面广，重点人群为老人、儿童、孕妇及慢性病患者。',
      '预防措施：1) 每年接种流感疫苗是最有效的预防手段；2) 勤洗手，使用肥皂或洗手液并用流动水冲洗；3) 在流感高发季避免前往人群密集场所，必要时佩戴口罩；4) 保持室内通风，均衡饮食，增强免疫力。',
      '出现持续高热、剧烈咳嗽、呼吸困难等症状应及时就诊，尤其是老年人与基础疾病患者。',
    ],
  },
  {
    id: 4,
    category: '体检解读',
    color: '#e6a23c',
    title: '体检报告常见指标解读',
    summary: '看懂血常规、血脂、血糖、肝功能等常用指标的含义。',
    date: '2026-08-12',
    content: [
      '血常规：白细胞升高常提示感染或炎症，血红蛋白偏低提示贫血，血小板异常需进一步检查。',
      '血脂四项：总胆固醇、甘油三酯、低密度脂蛋白胆固醇升高是心血管风险因素，高密度脂蛋白胆固醇被称为"好胆固醇"，越高越好。',
      '血糖：空腹血糖高于 6.1mmol/L 提示糖调节受损，需复查糖化血红蛋白或行口服葡萄糖耐量试验。',
      '肝功能：转氨酶升高常见于脂肪肝、肝炎等，建议结合腹部超声进一步评估。',
      '指标异常不等于患病，请携带报告咨询专业医生。',
    ],
  },
  {
    id: 5,
    category: '睡眠健康',
    color: '#b37feb',
    title: '科学睡眠：如何改善失眠',
    summary: '建立规律作息、营造良好睡眠环境、远离电子产品。',
    date: '2026-08-10',
    content: [
      '失眠表现为入睡困难、易醒、早醒，长期失眠会影响日间功能与情绪。',
      '改善建议：1) 固定起床时间，午睡不超过 30 分钟；2) 睡前 1 小时远离手机、电脑等电子屏幕；3) 卧室保持黑暗、安静、凉爽；4) 避免睡前饮酒、咖啡因与大量进食；5) 白天适度运动，但避免睡前剧烈运动。',
      '若失眠持续超过 1 个月并严重影响生活，建议到睡眠门诊或神经内科就诊。',
    ],
  },
  {
    id: 6,
    category: '妇幼健康',
    color: '#eb2f96',
    title: '儿童疫苗接种时间表（简要）',
    summary: '按时接种疫苗是预防儿童传染病最经济有效的手段。',
    date: '2026-08-08',
    content: [
      '我国儿童免疫规划疫苗按以下大致时间接种：出生时接种乙肝疫苗第 1 剂、卡介苗；2 月龄接种脊灰疫苗第 1 剂；3 月龄接种百白破第 1 剂、脊灰第 2 剂；6 月龄接种乙肝第 3 剂；8 月龄接种麻腮风；1 岁半接种百白破第 4 剂、麻腮风第 2 剂；2 岁、4 岁、6 岁分别有相应加强剂次。',
      '接种前请如实告知医生儿童健康状况；接种后留观 30 分钟。',
      '具体接种计划以当地疾控中心和接种门诊安排为准。',
    ],
  },
  {
    id: 7,
    category: '骨骼健康',
    color: '#409eff',
    title: '骨质疏松的预防与治疗',
    summary: '补钙、补维D、多运动，年轻时储备骨量，年老时减缓流失。',
    date: '2026-08-05',
    content: [
      '骨质疏松是一种以骨量减少、骨微结构破坏为特征的全身性骨病，好发于绝经后女性与老年人，可导致脆性骨折。',
      '预防要点：1) 保证钙摄入，成人每日约 800-1000mg，奶制品、豆制品、深绿色蔬菜是优质来源；2) 补充维生素 D，多晒太阳促进合成；3) 坚持负重运动如快走、慢跑、跳操；4) 戒烟限酒，避免长期使用糖皮质激素。',
      '已确诊者应遵医嘱使用抗骨质疏松药物，并注意预防跌倒。',
    ],
  },
  {
    id: 8,
    category: '心理健康',
    color: '#67c23a',
    title: '识别与应对焦虑情绪',
    summary: '适度焦虑是正常的，持续过度焦虑则需要重视与干预。',
    date: '2026-08-01',
    content: [
      '焦虑是对未来威胁或不确定性的正常反应，但当焦虑持续存在、过度强烈并影响工作生活时，需引起重视。',
      '应对方法：1) 进行腹式呼吸训练，缓解躯体紧张；2) 规律作息与运动，避免熬夜；3) 减少信息过载，限制焦虑源输入；4) 与亲友倾诉，建立支持网络；5) 必要时寻求心理科专业帮助，进行心理治疗或药物干预。',
      '如果出现持续情绪低落、失眠、兴趣减退超过 2 周，请及时就诊。',
    ],
  },
]

const keyword = ref('')
const dialogVisible = ref(false)
const current = ref<Article | null>(null)

const filteredArticles = computed(() => {
  const kw = keyword.value.trim()
  if (!kw) return articles
  return articles.filter(
    (a) => a.title.includes(kw) || a.summary.includes(kw) || a.category.includes(kw),
  )
})

function openArticle(article: Article) {
  current.value = article
  dialogVisible.value = true
}
</script>

<style scoped>
.article-col {
  margin-bottom: 16px;
}

.article-card {
  cursor: pointer;
  border-radius: 10px;
  transition: all 0.2s;
}

.article-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}

.article-cat {
  display: inline-block;
  color: #fff;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
}

.article-title {
  font-size: 16px;
  color: #303133;
  margin: 12px 0 8px;
}

.article-summary {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  min-height: 42px;
  margin: 0 0 12px;
}

.article-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #c0c4cc;
}

.article-read {
  color: #409eff;
}

.article-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #909399;
  font-size: 13px;
  margin-bottom: 14px;
}

.article-para {
  font-size: 14px;
  line-height: 1.9;
  color: #303133;
  margin: 0 0 12px;
  text-align: justify;
}

.disclaimer {
  margin-top: 18px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
