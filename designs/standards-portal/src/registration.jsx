import React, { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import policy from "./registration-policy.json";

const DEFER_KEY = "stds-registration-deferred-until";
const roleNames = {
  expert: "标准专家",
  vendor: "应用厂商",
  other: "其他参与者",
};
export async function registrationApi(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("登记服务响应异常，请稍后重试。");
  }
  if (!response.ok) throw new Error(result.error || "请求未完成，请稍后重试。");
  return result;
}
export function useRegistration(exempt = false) {
  const [open, setOpen] = useState(false);
  const [ready, setReady] = useState(false);
  const [record, setRecord] = useState(null);
  const [error, setError] = useState("");
  const refresh = async () => {
    setError("");
    try {
      const result = await registrationApi("/api/registration/session");
      setRecord(result.registration);
      return result.registration;
    } catch (failure) {
      setError(failure.message);
      return null;
    } finally {
      setReady(true);
    }
  };
  useEffect(() => {
    if (exempt) {
      setOpen(false);
      return;
    }
    let active = true;
    let deferred = false;
    try {
      deferred = Number(sessionStorage.getItem(DEFER_KEY)) > Date.now();
    } catch {
      /* Storage can be unavailable. */
    }
    registrationApi("/api/registration/session")
      .then((result) => {
        if (!active) return;
        setRecord(result.registration);
        setOpen(
          result.registration?.requiresConsent ||
            (!result.registration && !deferred),
        );
      })
      .catch((failure) => {
        if (active) {
          setError(failure.message);
          setOpen(!deferred);
        }
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, [exempt]);
  const defer = () => {
    try {
      sessionStorage.setItem(DEFER_KEY, String(Date.now() + 86400000));
    } catch {
      /* Declining never depends on browser storage. */
    }
    setOpen(false);
  };
  const saved = (value) => {
    setRecord(value);
    setError("");
    setOpen(false);
    try {
      sessionStorage.removeItem(DEFER_KEY);
    } catch {
      /* No personal data is stored here. */
    }
  };
  return {
    open,
    setOpen,
    ready,
    record,
    setRecord,
    error,
    refresh,
    defer,
    saved,
  };
}

function PolicySummary() {
  return (
    <details className="registration-notice">
      <summary>登记用途与隐私说明</summary>
      <div>
        <p>
          管理方：{policy.controller}。联系邮箱：
          <a href={`mailto:${policy.contactEmail}`}>{policy.contactEmail}</a>。
        </p>
        <p>{policy.purpose}</p>
        <p>
          姓名、单位或身份、参与角色用于组织评议；专业方向和邮箱选填。名单仅供获授权的组织方查看，不在网站公开。
        </p>
        <p>
          登记或更新后有效期为 {policy.retentionDays}{" "}
          天，到期从名单移除并由每日任务清理。可从“阅读登记”撤回，也可联系组织方申请更正、查阅或删除。
        </p>
        <p>
          {policy.storageNotice}服务方：{policy.processor}；
          <a href={policy.processorContact} target="_blank" rel="noreferrer">
            服务方隐私联系方式
          </a>
          。你可通过组织方邮箱行使相关权利。
        </p>
        <a href="/privacy/" target="_blank" rel="noreferrer">
          查看完整隐私说明
        </a>
      </div>
    </details>
  );
}

export function RegistrationDialog({ state }) {
  const dialogRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [fields, setFields] = useState({
    name: "",
    organization: "",
    role: "",
    field: "",
    email: "",
    allowContact: false,
  });
  const [consent, setConsent] = useState(false);
  const [internationalConsent, setInternationalConsent] = useState(false);
  const [withdraw, setWithdraw] = useState(false);
  const [actionNotice, setActionNotice] = useState("");
  useEffect(() => {
    if (!state.open) return;
    setFields(
      state.record
        ? {
            name: state.record.name,
            organization: state.record.organization,
            role: state.record.role,
            field: state.record.field,
            email: state.record.email,
            allowContact: state.record.allowContact,
          }
        : {
            name: "",
            organization: "",
            role: "",
            field: "",
            email: "",
            allowContact: false,
          },
    );
    setConsent(false);
    setInternationalConsent(false);
    setFailure("");
    setActionNotice("");
    setWithdraw(false);
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() =>
      dialogRef.current?.querySelector("input, button, summary")?.focus(),
    );
    return () => {
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
    };
  }, [state.open, state.record?.id]);
  if (!state.open) return null;
  const update = (key) => (event) =>
    setFields((current) => ({
      ...current,
      [key]:
        event.target.type === "checkbox"
          ? event.target.checked
          : event.target.value,
    }));
  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setFailure("");
    setBusy(true);
    try {
      const result = await registrationApi("/api/registration", {
        method: state.record ? "PUT" : "POST",
        headers: { "X-Reading-Entry": location.pathname },
        body: JSON.stringify({
          ...fields,
          consent,
          internationalConsent,
          consentVersion: policy.version,
        }),
      });
      state.saved(result.registration);
    } catch (error) {
      setFailure(error.message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    setBusy(true);
    setFailure("");
    try {
      await registrationApi("/api/registration", { method: "DELETE" });
      state.setRecord(null);
      await state.refresh();
      state.defer();
    } catch (error) {
      setFailure(error.message);
    } finally {
      setBusy(false);
    }
  };
  const confirmRead = async () => {
    setBusy(true);
    setFailure("");
    try {
      const result = await registrationApi(
        "/api/registration/read-confirmation",
        { method: "POST", body: JSON.stringify({ confirmed: true }) },
      );
      state.setRecord(result.registration);
      setActionNotice("已记录由本人确认的已阅状态。");
    } catch (error) {
      setFailure(error.message);
    } finally {
      setBusy(false);
    }
  };
  const trap = (event) => {
    if (event.key === "Escape" && !busy) {
      event.preventDefault();
      state.defer();
    }
    if (event.key === "Tab") {
      const items = [
        ...dialogRef.current.querySelectorAll(
          "button:not(:disabled),input:not([type=hidden]),select,summary,a",
        ),
      ].filter((element) => element.getClientRects().length);
      if (event.shiftKey && document.activeElement === items[0]) {
        event.preventDefault();
        items.at(-1)?.focus();
      } else if (!event.shiftKey && document.activeElement === items.at(-1)) {
        event.preventDefault();
        items[0]?.focus();
      }
    }
  };
  return (
    <div className="registration-overlay">
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="registration-title"
        aria-describedby="registration-purpose"
        className="registration-dialog"
        data-registration-dialog="true"
        onKeyDown={trap}
      >
        <header className="registration-heading">
          <div>
            <span className="eyebrow">PARTICIPATE IN THE REVIEW</span>
            <h2 id="registration-title">
              {state.record ? "管理阅读登记" : "阅读者登记"}
            </h2>
          </div>
          <button
            type="button"
            onClick={state.defer}
            disabled={busy}
            aria-label="关闭阅读登记"
          >
            <X size={20} />
          </button>
        </header>
        <p id="registration-purpose">
          请留下必要信息，便于编制组了解参与者并就标准评议交流。登记名单仅供组织方查看。
        </p>
        {!state.ready ? (
          <p className="registration-loading" role="status">
            正在连接登记服务…
          </p>
        ) : (
          <>
            <form onSubmit={submit}>
              <div className="registration-fields">
                <label>
                  姓名<span>必填</span>
                  <input
                    name="name"
                    autoComplete="name"
                    maxLength={60}
                    required
                    value={fields.name}
                    onChange={update("name")}
                  />
                </label>
                <label>
                  参与身份<span>必填</span>
                  <select
                    name="role"
                    required
                    value={fields.role}
                    onChange={update("role")}
                  >
                    <option value="">请选择</option>
                    {Object.entries(roleNames).map(([value, title]) => (
                      <option key={value} value={value}>
                        {title}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="full">
                  单位或身份<span>必填</span>
                  <input
                    name="organization"
                    autoComplete="organization"
                    maxLength={160}
                    required
                    placeholder="单位名称，或独立研究者等身份"
                    value={fields.organization}
                    onChange={update("organization")}
                  />
                </label>
                <label>
                  专业或业务方向<span>选填</span>
                  <input
                    name="field"
                    maxLength={120}
                    value={fields.field}
                    onChange={update("field")}
                  />
                </label>
                <label>
                  邮箱<span>选填</span>
                  <input
                    name="email"
                    autoComplete="email"
                    type="email"
                    maxLength={254}
                    value={fields.email}
                    onChange={update("email")}
                  />
                </label>
              </div>
              <label className="registration-check optional">
                <input
                  type="checkbox"
                  checked={fields.allowContact}
                  onChange={update("allowContact")}
                />
                愿意通过上述邮箱就评议意见接受后续联系
              </label>
              <PolicySummary />
              <label className="registration-check">
                <input
                  type="checkbox"
                  required
                  checked={consent}
                  onChange={(event) => setConsent(event.target.checked)}
                />
                我已阅读登记说明，同意为本次评议保存上述信息。
              </label>
              <label className="registration-check">
                <input
                  type="checkbox"
                  required
                  checked={internationalConsent}
                  onChange={(event) =>
                    setInternationalConsent(event.target.checked)
                  }
                />
                同意由隐私说明中列明的境外服务处理登记信息。
              </label>
              {(failure || state.error) && (
                <div className="registration-error" role="alert">
                  {failure || state.error}
                  {state.error && (
                    <button type="button" onClick={state.refresh}>
                      重试连接
                    </button>
                  )}
                </div>
              )}
              <div className="registration-actions">
                <button
                  className="button primary"
                  type="submit"
                  disabled={busy}
                >
                  {busy
                    ? "正在保存…"
                    : state.record
                      ? "保存修改"
                      : "登记并继续阅读"}
                  <ArrowRight size={16} />
                </button>
                <button
                  className="text-link"
                  type="button"
                  disabled={busy}
                  onClick={state.defer}
                >
                  {state.record ? "返回阅读" : "暂不登记，继续浏览"}
                </button>
              </div>
            </form>
            {state.record && (
              <div className="registration-manage">
                <div>
                  <ShieldCheck size={17} />
                  <span>
                    登记有效至{" "}
                    {new Date(state.record.expiresAt).toLocaleDateString(
                      "zh-CN",
                    )}
                  </span>
                </div>
                {state.record.readConfirmedAt ? (
                  <p>
                    <Check size={16} />
                    已由本人确认阅览：
                    {new Date(state.record.readConfirmedAt).toLocaleString(
                      "zh-CN",
                    )}
                  </p>
                ) : (
                  <button
                    type="button"
                    className="text-link"
                    disabled={busy}
                    onClick={confirmRead}
                  >
                    本人确认已阅本标准
                  </button>
                )}
                {actionNotice && <p role="status">{actionNotice}</p>}
                <p>
                  “已登记”与“本人确认已阅”分别记录，不依据访问或停留时间推定。
                </p>
                {withdraw ? (
                  <div className="withdraw-confirm">
                    <span>撤回将删除这条登记及其已阅状态。</span>
                    <button
                      type="button"
                      className="text-link danger"
                      disabled={busy}
                      onClick={remove}
                    >
                      确认撤回并删除
                    </button>
                    <button
                      type="button"
                      className="text-link"
                      onClick={() => setWithdraw(false)}
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="text-link danger"
                    onClick={() => setWithdraw(true)}
                  >
                    撤回登记
                  </button>
                )}
              </div>
            )}
          </>
        )}
        <footer className="registration-footer">
          <UserRound size={13} />
          {policy.controller}
          <a href={`mailto:${policy.contactEmail}`}>联系编制组</a>
        </footer>
      </section>
    </div>
  );
}

export function PrivacyPage() {
  return (
    <div className="topic-page page-enter" data-screen-label="阅读登记隐私说明">
      <p className="eyebrow">READER REGISTRATION PRIVACY</p>
      <h1>阅读登记隐私说明</h1>
      <p className="page-lead">
        适用于“智慧教学-数据模型标准”的阅读者登记，说明版本 {policy.version}
        。阅读标准本身可选择暂不登记。
      </p>
      <div className="privacy-prose">
        <h2>谁管理登记信息</h2>
        <p>
          {policy.controller}负责管理；联系邮箱：
          <a href={`mailto:${policy.contactEmail}`}>{policy.contactEmail}</a>。
        </p>
        <h2>用途与信息范围</h2>
        <p>
          {policy.purpose}
          登记包含姓名、单位或身份、参与角色，以及自愿填写的专业方向、邮箱和允许联系的选择。系统记录登记/更新时间、初始阅读入口、同意说明版本和期限；本人点击“确认已阅”后才记录该状态及时间。
        </p>
        <p>
          登记信息不在公开页面、搜索索引或 GitHub Issue
          中展示。不将页面打开、浏览时长或滚动位置作为完成审阅的证明；不建立浏览指纹和完整阅读轨迹。为防滥用，网络地址仅用于短时限流，不写入登记名单。
        </p>
        <h2>保存与受托处理</h2>
        <p>
          {policy.storageNotice}受托服务方为 {policy.processor}
          ，服务方联系方式见其
          <a href={policy.processorContact} target="_blank" rel="noreferrer">
            隐私政策
          </a>
          。组织方负责登记用途、访问管理和权利请求。跨境处理采用单独确认；不确认可继续浏览标准。
        </p>
        <p>
          主记录在每次登记或更新后有效期为 {policy.retentionDays}{" "}
          天，到期后立即从可用名单中移除，并由每日任务在 24
          小时内清理。撤回删除主记录后，云服务备份按服务自身恢复窗口到期清理，期间不恢复用于评议联系。
        </p>
        <h2>谁可以查看</h2>
        <p>
          只有获授权的编制组管理人员可以查看或导出名单，用于本次评议组织。公开署名或其他用途需另行征求意愿。管理端使用邮箱登录和独立的访问控制。
        </p>
        <h2>查阅、更正与撤回</h2>
        <p>
          同一浏览器可从顶部“阅读登记”查看、修改或撤回本人的登记。浏览器使用
          HttpOnly 不透明会话 Cookie
          关联登记，不在本地存储姓名、单位或邮箱；清理 Cookie 后可通过{" "}
          {policy.contactEmail} 联系组织方处理本人记录。撤回不影响继续浏览标准。
        </p>
        <p>
          你可以向上述邮箱提出查阅、更正、删除、撤回同意或投诉请求。允许后续联系的选择可以在修改登记时取消。
        </p>
      </div>
    </div>
  );
}
