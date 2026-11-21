import React from "react";
import { Download } from "lucide-react";
import data from "../generated.json";
import { readOnlyRevision } from "../shared.jsx";
export { Profiles, Roadmap, Decisions } from "../Topics.jsx";

export function Downloads() {
  return <div className="topic-page page-enter" data-screen-label="资料下载">
    <p className="eyebrow">{readOnlyRevision ? "STANDARD DOWNLOADS" : "INTERNAL PREVIEW DOCUMENTS"}</p>
    <h1>第2轮修订稿下载</h1>
    <p className="page-lead">{readOnlyRevision
      ? "在线正文、检索和下载使用同一份修订稿。"
      : "内部核对材料，非现行征求意见稿。在线正文、搜索和下载使用同一修订稿；评议意见汇总表沿用现有文件。"}</p>
    <div className="download-list">{data.downloads.map((file) => <a href={`/downloads/${file.file}`} download key={file.file}>
      <span className="file-type current">{file.type}</span>
      <div><h2>{file.title}</h2><p>{file.description}</p><small>{(file.bytes / 1024).toFixed(1)} KB</small></div>
      <Download size={21} />
    </a>)}</div>
  </div>;
}
