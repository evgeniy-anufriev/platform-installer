import { useMemo, useState } from "react";
import type {
  OpenResult,
  VerificationStatus,
  VerifiedPKIView,
} from "./backend";

export type CertificateIntent =
  | {
      operation:
        | "CreateCertificateAuthority"
        | "UpdateCertificateAuthority"
        | "CreateCertificateProfile"
        | "UpdateCertificateProfile"
        | "CreateTLSProfile"
        | "UpdateTLSProfile"
        | "CreateCertificateScope"
        | "UpdateCertificateScope";
      entityId: string;
      entity: Record<string, unknown>;
    }
  | {
      operation:
        | "DeleteCertificateAuthority"
        | "DeleteCertificateProfile"
        | "DeleteTLSProfile"
        | "DeleteCertificateScope";
      entityId: string;
    };

type PKIKind = "authority" | "profile" | "tls" | "scope";
type PKIEntity = Record<string, unknown>;
type Rows = Record<string, PKIEntity>;
export type CertificateSourceOptions = {
  hosts: string[];
  deployments: string[];
  members: Array<{ deploymentId: string; memberId: string }>;
};

const labels: Record<PKIKind, string> = {
  authority: "Managed CA",
  profile: "Certificate profiles",
  tls: "TLS profiles",
  scope: "Certificate scopes",
};
const operations: Record<
  PKIKind,
  {
    create: CertificateIntent["operation"];
    update: CertificateIntent["operation"];
    remove: CertificateIntent["operation"];
  }
> = {
  authority: {
    create: "CreateCertificateAuthority",
    update: "UpdateCertificateAuthority",
    remove: "DeleteCertificateAuthority",
  },
  profile: {
    create: "CreateCertificateProfile",
    update: "UpdateCertificateProfile",
    remove: "DeleteCertificateProfile",
  },
  tls: {
    create: "CreateTLSProfile",
    update: "UpdateTLSProfile",
    remove: "DeleteTLSProfile",
  },
  scope: {
    create: "CreateCertificateScope",
    update: "UpdateCertificateScope",
    remove: "DeleteCertificateScope",
  },
};

function rowsFor(
  kind: PKIKind,
  managed: OpenResult["managed"],
  intents: CertificateIntent[],
): Rows {
  const pki = managed?.pki;
  const source =
    kind === "authority"
      ? pki?.authorities
      : kind === "profile"
        ? pki?.profiles
        : kind === "tls"
          ? pki?.tlsProfiles
          : pki?.scopes;
  const rows: Rows = { ...(source || {}) };
  for (const intent of intents) {
    const operation = operations[kind];
    if (
      (intent.operation === operation.create ||
        intent.operation === operation.update) &&
      "entity" in intent
    )
      rows[intent.entityId] = intent.entity;
    if (intent.operation === operation.remove) delete rows[intent.entityId];
  }
  return rows;
}

const stringList = (value: unknown) =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
const listText = (value: unknown) => stringList(value).join(", ");
const parseList = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
const asRecord = (value: unknown): PKIEntity =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as PKIEntity)
    : {};

function secretRefLabel(value: unknown) {
  return typeof value === "string" && value.startsWith("runtime:")
    ? "runtime:••••"
    : "не задана";
}

export function CertificatesPage({
  managed,
  intents,
  busy,
  structuralDisabled,
  commandCount,
  sourceOptions,
  verification,
  verifiedPKI,
  onAppend,
  onReview,
  onDiscard,
  onVerify,
}: {
  managed: OpenResult["managed"];
  intents: CertificateIntent[];
  busy: boolean;
  structuralDisabled: boolean;
  commandCount: number;
  sourceOptions: CertificateSourceOptions;
  verification?: VerificationStatus;
  verifiedPKI?: VerifiedPKIView;
  onAppend: (intent: CertificateIntent) => Promise<boolean>;
  onReview: () => void;
  onDiscard: () => void;
  onVerify?: () => void;
}) {
  const [editor, setEditor] = useState<{ kind: PKIKind; id?: string } | null>(
    null,
  );
  const blocked = busy || structuralDisabled || commandCount >= 16;
  const allRows = useMemo(
    () => ({
      authority: rowsFor("authority", managed, intents),
      profile: rowsFor("profile", managed, intents),
      tls: rowsFor("tls", managed, intents),
      scope: rowsFor("scope", managed, intents),
    }),
    [managed, intents],
  );
  const remove = async (kind: PKIKind, entityId: string) => {
    if (
      await onAppend({
        operation: operations[kind].remove as CertificateIntent["operation"],
        entityId,
      } as CertificateIntent)
    )
      setEditor(null);
  };

  return (
    <section className="certificates-page">
      <div className="title">
        <div>
          <h1>Сертификаты</h1>
          <p>
            PKI intent проекта. Выпуск, materialization и применение здесь не
            выполняются.
          </p>
        </div>
        <DraftActions
          commandCount={commandCount}
          blocked={blocked}
          onReview={onReview}
          onDiscard={onDiscard}
        />
      </div>
      <p className="muted">
        Пустые поля наследуются из role defaults и не записываются. DNS/IP —
        прямые desired inputs; Core вычисляет identity и SAN после Verify.
      </p>
      {(Object.keys(labels) as PKIKind[]).map((kind) => (
        <article className="card certificate-section" key={kind}>
          <div className="section-head">
            <div>
              <h2>{labels[kind]}</h2>
              <small>{sectionHint(kind)}</small>
            </div>
            <button
              className="outline"
              disabled={blocked}
              onClick={() => setEditor({ kind })}
            >
              Добавить
            </button>
          </div>
          <CertificateRows
            kind={kind}
            rows={allRows[kind]}
            disabled={blocked}
            onEdit={(id) => setEditor({ kind, id })}
            onDelete={remove}
          />
        </article>
      ))}
      <CoreVerification
        verification={verification || { status: "UNVERIFIED" }}
        view={verifiedPKI}
        disabled={
          busy ||
          commandCount > 0 ||
          verification?.status === "VERIFYING" ||
          !onVerify
        }
        onVerify={onVerify || (() => undefined)}
      />
      {editor && (
        <CertificateDialog
          key={`${editor.kind}:${editor.id || "new"}`}
          kind={editor.kind}
          entityId={editor.id}
          entity={editor.id ? allRows[editor.kind][editor.id] : undefined}
          authorityIds={Object.keys(allRows.authority).sort()}
          profileIds={Object.keys(allRows.profile).sort()}
          sourceOptions={sourceOptions}
          disabled={blocked}
          onClose={() => setEditor(null)}
          onSubmit={async (entityId, entity) => {
            const operation = editor.id
              ? operations[editor.kind].update
              : operations[editor.kind].create;
            if (
              await onAppend({
                operation: operation as CertificateIntent["operation"],
                entityId,
                entity,
              } as CertificateIntent)
            )
              setEditor(null);
          }}
        />
      )}
    </section>
  );
}

function CoreVerification({
  verification,
  view,
  disabled,
  onVerify,
}: {
  verification: VerificationStatus;
  view?: VerifiedPKIView;
  disabled: boolean;
  onVerify: () => void;
}) {
  const status =
    view?.status ||
    (verification.status === "INVALID"
      ? "INVALID"
      : verification.status === "VERIFIED"
        ? "STALE"
        : verification.status === "VERIFYING"
          ? "NOT_VERIFIED"
          : "NOT_VERIFIED");
  const findings = view?.findings || verification.findings || [];
  return (
    <article className="card certificate-verification">
      <div className="section-head">
        <div>
          <h2>Проверка Core</h2>
          <small>
            Identity и SAN отображаются только из текущего Core evidence.
          </small>
        </div>
        <button disabled={disabled} onClick={onVerify}>
          {verification.status === "VERIFYING" ? "Проверка…" : "Проверить"}
        </button>
      </div>
      <p className="muted">
        Влияние provider VIP определяет Core после сохранения и проверки. Этот
        экран не создаёт сертификаты и не запускает reissue.
      </p>
      {status === "CURRENT" && view?.identities?.length ? (
        <div className="verified-identities">
          {view.identities.map((identity) => (
            <section key={identity.id} className="verified-identity">
              <b>{identity.id}</b>
              <small>
                {identity.scope} · TLS profile: {identity.tlsProfileId}
              </small>
              <div>
                <span>DNS: </span>
                {identity.dnsNames.join(", ") || "—"}
              </div>
              <div>
                <span>IP: </span>
                {identity.ipAddresses.join(", ") || "—"}
              </div>
              <div>
                <span>Consumers: </span>
                {identity.consumers
                  .map(
                    (consumer) =>
                      `${consumer.deploymentId}/${consumer.memberId} @ ${consumer.hostId}`,
                  )
                  .join(", ") || "—"}
              </div>
            </section>
          ))}
        </div>
      ) : status === "CURRENT" ? (
        <p className="muted">
          Core подтвердил проект; сертификатных consumers нет.
        </p>
      ) : (
        <p className={status === "INVALID" ? "field-error" : "muted"}>
          {verificationMessage(
            status,
            view?.error?.message || verification.error?.message,
          )}
        </p>
      )}
      {!!findings.length && (
        <ul className="verification-findings">
          {findings.map((finding, index) => (
            <li key={`${finding.code}:${finding.subjectId || index}`}>
              <b>{finding.code}</b>: {finding.summary}
              {finding.subjectId ? ` (${finding.subjectId})` : ""}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function verificationMessage(status: string, error?: string) {
  switch (status) {
    case "INVALID":
      return "Core обнаружил ошибки проверки. Сохранённый проект не откатывается.";
    case "STALE":
      return "Проверка устарела: сохраните изменения и запустите проверку снова.";
    case "UNAVAILABLE":
      return error || "Для проверки нужен READY Execution Node.";
    default:
      return "Проект ещё не проверен Core.";
  }
}

function sectionHint(kind: PKIKind) {
  if (kind === "authority") return "Только MANAGED CA.";
  if (kind === "profile") return "CA, usages, SAN policy и subject overrides.";
  if (kind === "tls") return "Только ссылка на runtime secret, без пароля.";
  return "Источники hosts, deployments, members и явные DNS/IP.";
}

function DraftActions({
  commandCount,
  blocked,
  onReview,
  onDiscard,
}: {
  commandCount: number;
  blocked: boolean;
  onReview: () => void;
  onDiscard: () => void;
}) {
  return (
    <div className="actions">
      <span className="muted">{commandCount} / 16 изменений</span>
      {commandCount > 0 && (
        <>
          <button className="outline" disabled={blocked} onClick={onDiscard}>
            Отменить изменения
          </button>
          <button disabled={blocked} onClick={onReview}>
            Просмотреть изменения
          </button>
        </>
      )}
    </div>
  );
}

function CertificateRows({
  kind,
  rows,
  disabled,
  onEdit,
  onDelete,
}: {
  kind: PKIKind;
  rows: Rows;
  disabled: boolean;
  onEdit: (id: string) => void;
  onDelete: (kind: PKIKind, id: string) => Promise<void>;
}) {
  const values = Object.entries(rows).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  if (!values.length)
    return <p className="muted">Нет сохранённых или черновых записей.</p>;
  return (
    <div className="certificate-rows">
      {values.map(([id, entity]) => (
        <div className="certificate-row" key={id}>
          <div>
            <b>{id}</b>
            <small>{rowSummary(kind, entity)}</small>
          </div>
          <div className="actions">
            <button
              className="link"
              disabled={disabled}
              onClick={() => onEdit(id)}
            >
              Изменить
            </button>
            <button
              className="link danger"
              disabled={disabled}
              onClick={() => void onDelete(kind, id)}
            >
              Удалить
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function rowSummary(kind: PKIKind, entity: PKIEntity) {
  if (kind === "authority") return String(entity.commonName || "MANAGED");
  if (kind === "profile") return `CA: ${String(entity.authorityRef || "—")}`;
  if (kind === "tls")
    return `Profile: ${String(entity.certificateProfileRef || "—")} · ${secretRefLabel(entity.storePasswordSecretRef)}`;
  return `Profile: ${String(entity.profile || "—")} · ${Object.keys(asRecord(entity.sources)).length} sources`;
}

function CertificateDialog({
  kind,
  entityId,
  entity,
  authorityIds,
  profileIds,
  sourceOptions,
  disabled,
  onClose,
  onSubmit,
}: {
  kind: PKIKind;
  entityId?: string;
  entity?: PKIEntity;
  authorityIds: string[];
  profileIds: string[];
  sourceOptions: CertificateSourceOptions;
  disabled: boolean;
  onClose: () => void;
  onSubmit: (id: string, entity: PKIEntity) => Promise<void>;
}) {
  const existing = asRecord(entity);
  const [id, setID] = useState(entityId || "");
  const [displayName, setDisplayName] = useState(
    String(existing.displayName || ""),
  );
  const [commonName, setCommonName] = useState(
    String(existing.commonName || ""),
  );
  const [authorityRef, setAuthorityRef] = useState(
    String(existing.authorityRef || authorityIds[0] || ""),
  );
  const [profileRef, setProfileRef] = useState(
    String(
      existing.certificateProfileRef || existing.profile || profileIds[0] || "",
    ),
  );
  const [scope, setScope] = useState(String(existing.scope || ""));
  const [secretRef, setSecretRef] = useState(
    String(existing.storePasswordSecretRef || ""),
  );
  const [secretInput, setSecretInput] = useState("");
  const [keyAlgorithm, setKeyAlgorithm] = useState(
    String(existing.keyAlgorithm || ""),
  );
  const [keySize, setKeySize] = useState(
    existing.keySize === undefined ? "" : String(existing.keySize),
  );
  const [validityDays, setValidityDays] = useState(
    existing.validityDays === undefined ? "" : String(existing.validityDays),
  );
  const [usages, setUsages] = useState(stringList(existing.usages));
  const [usagesPresent, setUsagesPresent] = useState(
    Object.hasOwn(existing, "usages"),
  );
  const [sanPolicy, setSanPolicy] = useState(asRecord(existing.sanPolicy));
  const [subject, setSubject] = useState(asRecord(existing.subject));
  const sources = asRecord(existing.sources);
  const [hosts, setHosts] = useState(stringList(sources.hosts));
  const [deployments, setDeployments] = useState(
    stringList(sources.serviceDeployments),
  );
  const [members, setMembers] = useState(
    (Array.isArray(sources.members) ? sources.members : []).flatMap((item) => {
      const value = asRecord(item);
      const deploymentId = value.deploymentId;
      const memberId = value.memberId;
      return typeof deploymentId === "string" && typeof memberId === "string"
        ? [{ deploymentId, memberId }]
        : [];
    }),
  );
  const [dnsNames, setDnsNames] = useState(listText(sources.explicitDnsNames));
  const [ipAddresses, setIPAddresses] = useState(
    listText(sources.explicitIpAddresses),
  );
  const [error, setError] = useState("");
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!id.trim()) return setError("Укажите ID записи.");
    const result = entityFor(kind, {
      displayName,
      commonName,
      authorityRef,
      profileRef,
      scope,
      secretRef: secretInput.trim() || secretRef,
      keyAlgorithm,
      keySize,
      validityDays,
      usages,
      usagesPresent,
      sanPolicy,
      subject,
      hosts,
      deployments,
      members,
      dnsNames,
      ipAddresses,
    });
    if (!result) return setError("Проверьте поля Certificate Scope.");
    setError("");
    await onSubmit(id.trim(), result);
  };
  return (
    <div className="modal" role="presentation">
      <form className="card dialog certificate-dialog" onSubmit={submit}>
        <h1>
          {entityId ? "Изменить" : "Добавить"}: {labels[kind]}
        </h1>
        <label>
          ID
          <input
            value={id}
            disabled={!!entityId || disabled}
            onChange={(event) => setID(event.target.value)}
            autoFocus
          />
        </label>
        {kind !== "tls" && (
          <OptionalText
            label="Отображаемое имя"
            value={displayName}
            onChange={setDisplayName}
          />
        )}
        {kind === "authority" && (
          <>
            <label>
              Common Name
              <input
                value={commonName}
                onChange={(event) => setCommonName(event.target.value)}
                required
              />
            </label>
            <OptionalNumber
              label="Validity days"
              value={validityDays}
              onChange={setValidityDays}
            />
          </>
        )}
        {kind === "profile" && (
          <ProfileFields
            authorityRef={authorityRef}
            authorityIds={authorityIds}
            onAuthorityRef={setAuthorityRef}
            keyAlgorithm={keyAlgorithm}
            onKeyAlgorithm={setKeyAlgorithm}
            keySize={keySize}
            onKeySize={setKeySize}
            validityDays={validityDays}
            onValidityDays={setValidityDays}
            usages={usages}
            onUsages={(value) => {
              setUsagesPresent(true);
              setUsages(value);
            }}
            sanPolicy={sanPolicy}
            onSanPolicy={setSanPolicy}
            subject={subject}
            onSubject={setSubject}
          />
        )}
        {kind === "tls" && (
          <>
            <ReferenceSelect
              label="Certificate profile"
              value={profileRef}
              values={profileIds}
              onChange={setProfileRef}
            />
            <label>
              Scope
              <select
                value={scope}
                onChange={(event) => setScope(event.target.value)}
              >
                <option value="">Inherited</option>
                <option>HOST</option>
                <option>MEMBER</option>
                <option>DEPLOYMENT</option>
              </select>
            </label>
            <label>
              Runtime SecretRef
              <input
                value={secretInput}
                onChange={(event) => {
                  setSecretInput(event.target.value);
                  setSecretRef(event.target.value);
                }}
                placeholder={
                  secretRef
                    ? "Ссылка сохранена; введите новую для замены"
                    : "runtime:tls-store"
                }
                required={!secretRef}
              />
            </label>
            <p className="muted">
              Пароль не вводится, не отображается и не проверяется. Сохраняется
              только runtime reference.
            </p>
          </>
        )}
        {kind === "scope" && (
          <ScopeFields
            profileRef={profileRef}
            profileIds={profileIds}
            onProfileRef={setProfileRef}
            scope={scope}
            onScope={setScope}
            hosts={hosts}
            onHosts={setHosts}
            deployments={deployments}
            onDeployments={setDeployments}
            members={members}
            onMembers={setMembers}
            sourceOptions={sourceOptions}
            dnsNames={dnsNames}
            onDNSNames={setDnsNames}
            ipAddresses={ipAddresses}
            onIPAddresses={setIPAddresses}
          />
        )}
        {error && <p className="field-error">{error}</p>}
        <div className="actions">
          <button type="button" className="outline" onClick={onClose}>
            Отмена
          </button>
          <button disabled={disabled} type="submit">
            Добавить в черновик
          </button>
        </div>
      </form>
    </div>
  );
}

function OptionalText({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Inherited"
      />
    </label>
  );
}
function OptionalNumber({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <input
        type="number"
        min="1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Inherited"
      />
    </label>
  );
}
function ReferenceSelect({
  label,
  value,
  values,
  onChange,
}: {
  label: string;
  value: string;
  values: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required
      >
        <option value="">Выберите</option>
        {values.map((item) => (
          <option key={item}>{item}</option>
        ))}
      </select>
    </label>
  );
}

function ProfileFields(props: {
  authorityRef: string;
  authorityIds: string[];
  onAuthorityRef: (value: string) => void;
  keyAlgorithm: string;
  onKeyAlgorithm: (value: string) => void;
  keySize: string;
  onKeySize: (value: string) => void;
  validityDays: string;
  onValidityDays: (value: string) => void;
  usages: string[];
  onUsages: (value: string[]) => void;
  sanPolicy: PKIEntity;
  onSanPolicy: (value: PKIEntity) => void;
  subject: PKIEntity;
  onSubject: (value: PKIEntity) => void;
}) {
  const policyKeys = [
    "includeHostDns",
    "includeHostIp",
    "includeEndpointFqdns",
    "includeEndpointWildcard",
    "includeEndpointVip",
  ];
  return (
    <>
      <ReferenceSelect
        label="Certificate authority"
        value={props.authorityRef}
        values={props.authorityIds}
        onChange={props.onAuthorityRef}
      />
      <label>
        Key algorithm
        <select
          value={props.keyAlgorithm}
          onChange={(event) => props.onKeyAlgorithm(event.target.value)}
        >
          <option value="">Inherited</option>
          <option>RSA</option>
          <option>EC</option>
        </select>
      </label>
      <OptionalNumber
        label="Key size"
        value={props.keySize}
        onChange={props.onKeySize}
      />
      <OptionalNumber
        label="Validity days"
        value={props.validityDays}
        onChange={props.onValidityDays}
      />
      <fieldset>
        <legend>Usages</legend>
        {["serverAuth", "clientAuth"].map((usage) => (
          <label key={usage}>
            <input
              type="checkbox"
              checked={props.usages.includes(usage)}
              onChange={(event) =>
                props.onUsages(
                  event.target.checked
                    ? [...props.usages, usage]
                    : props.usages.filter((item) => item !== usage),
                )
              }
            />
            {usage}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>SAN policy overrides</legend>
        {policyKeys.map((key) => (
          <label key={key}>
            {key}
            <select
              aria-label={key}
              value={
                typeof props.sanPolicy[key] === "boolean"
                  ? String(props.sanPolicy[key])
                  : ""
              }
              onChange={(event) => {
                const next = { ...props.sanPolicy };
                if (event.target.value === "") delete next[key];
                else next[key] = event.target.value === "true";
                props.onSanPolicy(next);
              }}
            >
              <option value="">Inherited</option>
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Subject overrides</legend>
        {["C", "ST", "L", "O", "OU"].map((key) => (
          <label key={key}>
            {key}
            <input
              value={String(props.subject[key] || "")}
              onChange={(event) =>
                props.onSubject({ ...props.subject, [key]: event.target.value })
              }
            />
          </label>
        ))}
      </fieldset>
    </>
  );
}

function ScopeFields(props: {
  profileRef: string;
  profileIds: string[];
  onProfileRef: (value: string) => void;
  scope: string;
  onScope: (value: string) => void;
  hosts: string[];
  onHosts: (value: string[]) => void;
  deployments: string[];
  onDeployments: (value: string[]) => void;
  members: Array<{ deploymentId: string; memberId: string }>;
  onMembers: (value: Array<{ deploymentId: string; memberId: string }>) => void;
  sourceOptions: CertificateSourceOptions;
  dnsNames: string;
  onDNSNames: (value: string) => void;
  ipAddresses: string;
  onIPAddresses: (value: string) => void;
}) {
  return (
    <>
      <ReferenceSelect
        label="Certificate profile"
        value={props.profileRef}
        values={props.profileIds}
        onChange={props.onProfileRef}
      />
      <label>
        Scope
        <select
          value={props.scope}
          onChange={(event) => props.onScope(event.target.value)}
        >
          <option value="">Inherited</option>
          <option>HOST</option>
          <option>MEMBER</option>
          <option>DEPLOYMENT</option>
        </select>
      </label>
      <ReferenceChoices
        label="Hosts"
        values={props.sourceOptions.hosts}
        selected={props.hosts}
        onChange={props.onHosts}
      />
      <ReferenceChoices
        label="Deployments"
        values={props.sourceOptions.deployments}
        selected={props.deployments}
        onChange={props.onDeployments}
      />
      <MemberChoices
        values={props.sourceOptions.members}
        selected={props.members}
        onChange={props.onMembers}
      />
      <OptionalText
        label="Explicit DNS names"
        value={props.dnsNames}
        onChange={props.onDNSNames}
      />
      <OptionalText
        label="Explicit IP addresses"
        value={props.ipAddresses}
        onChange={props.onIPAddresses}
      />
    </>
  );
}

function ReferenceChoices({
  label,
  values,
  selected,
  onChange,
}: {
  label: string;
  values: string[];
  selected: string[];
  onChange: (value: string[]) => void;
}) {
  const options = [...new Set([...values, ...selected])].sort();
  return (
    <fieldset>
      <legend>{label}</legend>
      {!options.length && (
        <small>Нет доступных записей в текущем черновике.</small>
      )}
      {options.map((value) => (
        <label key={value}>
          <input
            type="checkbox"
            checked={selected.includes(value)}
            onChange={(event) =>
              onChange(
                event.target.checked
                  ? [...selected, value]
                  : selected.filter((item) => item !== value),
              )
            }
          />
          {value}
        </label>
      ))}
    </fieldset>
  );
}

function MemberChoices({
  values,
  selected,
  onChange,
}: {
  values: Array<{ deploymentId: string; memberId: string }>;
  selected: Array<{ deploymentId: string; memberId: string }>;
  onChange: (value: Array<{ deploymentId: string; memberId: string }>) => void;
}) {
  const key = (value: { deploymentId: string; memberId: string }) =>
    `${value.deploymentId}\u0000${value.memberId}`;
  const options = [
    ...new Map(
      [...values, ...selected].map((value) => [key(value), value]),
    ).values(),
  ];
  return (
    <fieldset>
      <legend>Members</legend>
      {!options.length && (
        <small>Нет member-scoped placement в текущем черновике.</small>
      )}
      {options.map((value) => (
        <label key={key(value)}>
          <input
            type="checkbox"
            checked={selected.some((item) => key(item) === key(value))}
            onChange={(event) =>
              onChange(
                event.target.checked
                  ? [...selected, value]
                  : selected.filter((item) => key(item) !== key(value)),
              )
            }
          />
          {value.deploymentId}/{value.memberId}
        </label>
      ))}
    </fieldset>
  );
}

function entityFor(
  kind: PKIKind,
  input: {
    displayName: string;
    commonName: string;
    authorityRef: string;
    profileRef: string;
    scope: string;
    secretRef: string;
    keyAlgorithm: string;
    keySize: string;
    validityDays: string;
    usages: string[];
    usagesPresent: boolean;
    sanPolicy: PKIEntity;
    subject: PKIEntity;
    hosts: string[];
    deployments: string[];
    members: Array<{ deploymentId: string; memberId: string }>;
    dnsNames: string;
    ipAddresses: string;
  },
): PKIEntity | null {
  const optional = (value: string) => value.trim() || undefined;
  const number = (value: string) => (value.trim() ? Number(value) : undefined);
  if (kind === "authority")
    return {
      mode: "MANAGED",
      commonName: input.commonName.trim(),
      ...(optional(input.displayName) && {
        displayName: optional(input.displayName),
      }),
      ...(number(input.validityDays) !== undefined && {
        validityDays: number(input.validityDays),
      }),
    };
  if (kind === "profile") {
    const subject = Object.fromEntries(
      Object.entries(input.subject).filter(([, value]) => String(value).trim()),
    );
    return {
      authorityRef: input.authorityRef,
      sanPolicy: input.sanPolicy,
      ...(optional(input.displayName) && {
        displayName: optional(input.displayName),
      }),
      ...(optional(input.keyAlgorithm) && {
        keyAlgorithm: optional(input.keyAlgorithm),
      }),
      ...(number(input.keySize) !== undefined && {
        keySize: number(input.keySize),
      }),
      ...(number(input.validityDays) !== undefined && {
        validityDays: number(input.validityDays),
      }),
      ...(input.usagesPresent && { usages: input.usages }),
      ...(Object.keys(subject).length && { subject }),
    };
  }
  if (kind === "tls")
    return {
      certificateProfileRef: input.profileRef,
      storePasswordSecretRef: input.secretRef.trim(),
      ...(optional(input.scope) && { scope: optional(input.scope) }),
    };
  const sources: PKIEntity = {};
  const add = (key: string, values: string[]) => {
    if (values.length) sources[key] = values;
  };
  add("hosts", input.hosts);
  add("serviceDeployments", input.deployments);
  if (input.members.length) sources.members = input.members;
  add("explicitDnsNames", parseList(input.dnsNames));
  add("explicitIpAddresses", parseList(input.ipAddresses));
  return {
    profile: input.profileRef,
    sources,
    ...(optional(input.displayName) && {
      displayName: optional(input.displayName),
    }),
    ...(optional(input.scope) && { scope: optional(input.scope) }),
  };
}
