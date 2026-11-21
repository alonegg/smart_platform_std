import React from "react";
import { readOnlyRevision } from "../shared.jsx";
export { QuickStart } from "../Consultation.jsx";
export { deadlineText } from "../Consultation.jsx";
export const useCommentStats = () => null;

export function ConsultationStrip() {
  if (readOnlyRevision) return null;
  return <div className="consultation-strip" role="note">内部预览：意见提交和阅读登记已停用，不写入数据库。</div>;
}
export function CommentPage() {
  return <div className="topic-page"><h1>预览站不接收意见</h1><p>第2轮修订稿仅供内部核对。意见表单已禁用，不提交或保存任何意见。</p><button type="button" disabled>意见提交已禁用</button></div>;
}
export function ResponsesPage() {
  return <div className="topic-page"><h1>预览站不提供意见处理服务</h1><p>本预览站不连接现行征求意见稿的意见数据库。</p></div>;
}
