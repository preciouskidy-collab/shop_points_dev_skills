/**
 * 类别信息配置（数组形式，顺序即为显示顺序）
 *
 * Shop Points 后端 Skill 工具集包含以下四个类别：
 * - backend: Java/Spring Boot 后端开发技能
 * - common: 跨领域通用工具
 * - agents: 编排型 Agent，协调多个 skill 完成复杂工作流
 * - req-to-dev: 从飞书需求文档到技术方案再到代码开发的端到端工作流
 */
const CATEGORY_INFO = [
  {
    id: 'common',
    name: '通用技能',
    description: '调试、Git 辅助、Skill 创建器等跨领域通用开发工具'
  },
  {
    id: 'req-to-dev',
    name: '需求到开发',
    description: '从飞书 PRD 到需求分析、编码、审查、测试、发布的端到端工作流'
  },
  {
    id: 'guardrails',
    name: '编码守则',
    description: 'AI Agent 编码时必须遵守的分层约束和业务红线'
  },
  {
    id: 'knowledge',
    name: '系统知识',
    description: '按项目组织的架构、数据库、消息流等系统事实（shop-points / shop-points-lottery + 跨服务）'
  },
  {
    id: 'playbooks',
    name: '操作手册',
    description: '需求拆解、范围评估、编码、审查、测试等可复用 SOP'
  },
  {
    id: 'runtime',
    name: 'Agent Runtime',
    description: 'Pipeline 定义、触发规则、失败恢复、观测度量'
  },
];

module.exports = { CATEGORY_INFO };
