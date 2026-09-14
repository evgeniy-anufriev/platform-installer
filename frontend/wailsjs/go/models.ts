export namespace appconfig {
  export class ServerType {
    id: string;
    displayName: string;

    static createFrom(source: any = {}) {
      return new ServerType(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.displayName = source["displayName"];
    }
  }
  export class Config {
    schemaVersion: number;
    serverTypes: ServerType[];

    static createFrom(source: any = {}) {
      return new Config(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.schemaVersion = source["schemaVersion"];
      this.serverTypes = this.convertValues(source["serverTypes"], ServerType);
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
}

export namespace coreadapter {
  export class Document {
    logicalPath: string;
    digest: string;
    ownership: string;
    revisionIncluded: boolean;

    static createFrom(source: any = {}) {
      return new Document(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.logicalPath = source["logicalPath"];
      this.digest = source["digest"];
      this.ownership = source["ownership"];
      this.revisionIncluded = source["revisionIncluded"];
    }
  }
  export class Snapshot {
    status: string;
    partial: boolean;
    project: Record<string, any>;
    projectRevision: string;
    snapshotFingerprint: string;
    documents: Document[];
    hosts: Record<string, any>;
    serviceCatalog: Record<string, any>;
    serviceDeployments: Record<string, any>;
    effectiveConfiguration: Record<string, any>;
    endpointGroups: Record<string, any>;
    topology: Record<string, any>;
    endpoints: Record<string, any>;
    integrations: Record<string, any>;
    pki: Record<string, any>;
    validation: Record<string, any>;
    readiness: Record<string, any>;
    findings: any[];

    static createFrom(source: any = {}) {
      return new Snapshot(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.partial = source["partial"];
      this.project = source["project"];
      this.projectRevision = source["projectRevision"];
      this.snapshotFingerprint = source["snapshotFingerprint"];
      this.documents = this.convertValues(source["documents"], Document);
      this.hosts = source["hosts"];
      this.serviceCatalog = source["serviceCatalog"];
      this.serviceDeployments = source["serviceDeployments"];
      this.effectiveConfiguration = source["effectiveConfiguration"];
      this.endpointGroups = source["endpointGroups"];
      this.topology = source["topology"];
      this.endpoints = source["endpoints"];
      this.integrations = source["integrations"];
      this.pki = source["pki"];
      this.validation = source["validation"];
      this.readiness = source["readiness"];
      this.findings = source["findings"];
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
}

export namespace installer {
  export class CommitTiming {
    transaction: number;
    snapshot: number;

    static createFrom(source: any = {}) {
      return new CommitTiming(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.transaction = source["transaction"];
      this.snapshot = source["snapshot"];
    }
  }
  export class DocumentState {
    state: string;
    digest?: string;

    static createFrom(source: any = {}) {
      return new DocumentState(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.state = source["state"];
      this.digest = source["digest"];
    }
  }
  export class DocumentChange {
    logicalPath: string;
    beforeDigest?: string;
    afterDigest?: string;
    before?: DocumentState;
    after?: DocumentState;

    static createFrom(source: any = {}) {
      return new DocumentChange(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.logicalPath = source["logicalPath"];
      this.beforeDigest = source["beforeDigest"];
      this.afterDigest = source["afterDigest"];
      this.before = this.convertValues(source["before"], DocumentState);
      this.after = this.convertValues(source["after"], DocumentState);
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }

  export class PlacementMember {
    memberId: string;
    hostId: string;
    roles: string[];
    configuration?: Record<string, any>;

    static createFrom(source: any = {}) {
      return new PlacementMember(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.memberId = source["memberId"];
      this.hostId = source["hostId"];
      this.roles = source["roles"];
      this.configuration = source["configuration"];
    }
  }
  export class EditCommand {
    apiVersion?: string;
    kind?: string;
    baseProjectRevision?: string;
    operation: string;
    deploymentId?: string;
    setting?: string;
    value?: any;
    endpointGroupId?: string;
    haproxyDeploymentId?: string;
    hostId?: string;
    type?: string;
    address?: string;
    sshPort?: number;
    clearSSHPort?: boolean;
    serviceType?: string;
    mode?: string;
    entityId?: string;
    entity?: Record<string, any>;
    members?: PlacementMember[];
    property?: string;
    deployment?: Record<string, any>;
    endpointGroup?: Record<string, any>;
    placement?: Record<string, any>;
    backend?: Record<string, any>;
    commands?: EditCommand[];

    static createFrom(source: any = {}) {
      return new EditCommand(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.baseProjectRevision = source["baseProjectRevision"];
      this.operation = source["operation"];
      this.deploymentId = source["deploymentId"];
      this.setting = source["setting"];
      this.value = source["value"];
      this.endpointGroupId = source["endpointGroupId"];
      this.haproxyDeploymentId = source["haproxyDeploymentId"];
      this.hostId = source["hostId"];
      this.type = source["type"];
      this.address = source["address"];
      this.sshPort = source["sshPort"];
      this.clearSSHPort = source["clearSSHPort"];
      this.serviceType = source["serviceType"];
      this.mode = source["mode"];
      this.entityId = source["entityId"];
      this.entity = source["entity"];
      this.members = this.convertValues(source["members"], PlacementMember);
      this.property = source["property"];
      this.deployment = source["deployment"];
      this.endpointGroup = source["endpointGroup"];
      this.placement = source["placement"];
      this.backend = source["backend"];
      this.commands = this.convertValues(source["commands"], EditCommand);
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
  export class Finding {
    apiVersion: string;
    kind: string;
    code: string;
    status: string;
    category: string;
    field: string;
    safeMessage: string;

    static createFrom(source: any = {}) {
      return new Finding(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.code = source["code"];
      this.status = source["status"];
      this.category = source["category"];
      this.field = source["field"];
      this.safeMessage = source["safeMessage"];
    }
  }
  export class EditCommitResult {
    apiVersion: string;
    kind: string;
    status: string;
    changed: boolean;
    finding?: Finding;
    oldProjectRevision?: string;
    newProjectRevision?: string;
    affectedDocuments?: DocumentChange[];
    snapshot?: any;
    applyRequired: boolean;
    discarded?: boolean;
    timing: CommitTiming;

    static createFrom(source: any = {}) {
      return new EditCommitResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.status = source["status"];
      this.changed = source["changed"];
      this.finding = this.convertValues(source["finding"], Finding);
      this.oldProjectRevision = source["oldProjectRevision"];
      this.newProjectRevision = source["newProjectRevision"];
      this.affectedDocuments = this.convertValues(
        source["affectedDocuments"],
        DocumentChange,
      );
      this.snapshot = source["snapshot"];
      this.applyRequired = source["applyRequired"];
      this.discarded = source["discarded"];
      this.timing = this.convertValues(source["timing"], CommitTiming);
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
  export class PlanTiming {
    application: number;
    initialSnapshot: number;
    stagedSnapshot: number;

    static createFrom(source: any = {}) {
      return new PlanTiming(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.application = source["application"];
      this.initialSnapshot = source["initialSnapshot"];
      this.stagedSnapshot = source["stagedSnapshot"];
    }
  }
  export class Validation {
    status: string;
    findings: Finding[];

    static createFrom(source: any = {}) {
      return new Validation(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.findings = this.convertValues(source["findings"], Finding);
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
  export class SemanticChange {
    operation: string;
    entityId?: string;
    property?: string;
    safeSummary: string;

    static createFrom(source: any = {}) {
      return new SemanticChange(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.operation = source["operation"];
      this.entityId = source["entityId"];
      this.property = source["property"];
      this.safeSummary = source["safeSummary"];
    }
  }
  export class EditPlan {
    apiVersion: string;
    kind: string;
    status: string;
    planId?: string;
    baseProjectRevision: string;
    commandSummary: SemanticChange;
    semanticChanges: SemanticChange[];
    affectedEntities: string[];
    affectedDocuments: DocumentChange[];
    impacts: string[];
    validation: Validation;
    expectedEffectiveState?: any[];
    expectedSnapshotFingerprint?: string;
    reviewDiff: string;
    commitAllowed: boolean;
    applyRequired: boolean;
    // Go type: time
    expiresAt?: any;
    timing: PlanTiming;

    static createFrom(source: any = {}) {
      return new EditPlan(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.status = source["status"];
      this.planId = source["planId"];
      this.baseProjectRevision = source["baseProjectRevision"];
      this.commandSummary = this.convertValues(
        source["commandSummary"],
        SemanticChange,
      );
      this.semanticChanges = this.convertValues(
        source["semanticChanges"],
        SemanticChange,
      );
      this.affectedEntities = source["affectedEntities"];
      this.affectedDocuments = this.convertValues(
        source["affectedDocuments"],
        DocumentChange,
      );
      this.impacts = source["impacts"];
      this.validation = this.convertValues(source["validation"], Validation);
      this.expectedEffectiveState = source["expectedEffectiveState"];
      this.expectedSnapshotFingerprint = source["expectedSnapshotFingerprint"];
      this.reviewDiff = source["reviewDiff"];
      this.commitAllowed = source["commitAllowed"];
      this.applyRequired = source["applyRequired"];
      this.expiresAt = this.convertValues(source["expiresAt"], null);
      this.timing = this.convertValues(source["timing"], PlanTiming);
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
  export class EditSession {
    apiVersion: string;
    kind: string;
    sessionId: string;
    projectContextId: string;
    baseProjectRevision: string;
    status: string;
    commandCount: number;
    encodedBytes: number;
    // Go type: time
    expiresAt: any;
    reviewedPlanId?: string;

    static createFrom(source: any = {}) {
      return new EditSession(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.sessionId = source["sessionId"];
      this.projectContextId = source["projectContextId"];
      this.baseProjectRevision = source["baseProjectRevision"];
      this.status = source["status"];
      this.commandCount = source["commandCount"];
      this.encodedBytes = source["encodedBytes"];
      this.expiresAt = this.convertValues(source["expiresAt"], null);
      this.reviewedPlanId = source["reviewedPlanId"];
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
}

export namespace main {
  export class ProjectOpenError {
    code: string;
    message: string;

    static createFrom(source: any = {}) {
      return new ProjectOpenError(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.code = source["code"];
      this.message = source["message"];
    }
  }
  export class ApplicationConfigResult {
    status: string;
    config?: appconfig.Config;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new ApplicationConfigResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.config = this.convertValues(source["config"], appconfig.Config);
      this.error = this.convertValues(source["error"], ProjectOpenError);
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
  export class ApplicationDiagnostic {
    code: string;
    severity: string;
    hostId?: string;
    safeMessage: string;

    static createFrom(source: any = {}) {
      return new ApplicationDiagnostic(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.code = source["code"];
      this.severity = source["severity"];
      this.hostId = source["hostId"];
      this.safeMessage = source["safeMessage"];
    }
  }
  export class EditOperationResult {
    status: string;
    session?: installer.EditSession;
    plan?: installer.EditPlan;
    commit?: installer.EditCommitResult;
    diagnostics?: ApplicationDiagnostic[];
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new EditOperationResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.session = this.convertValues(
        source["session"],
        installer.EditSession,
      );
      this.plan = this.convertValues(source["plan"], installer.EditPlan);
      this.commit = this.convertValues(
        source["commit"],
        installer.EditCommitResult,
      );
      this.diagnostics = this.convertValues(
        source["diagnostics"],
        ApplicationDiagnostic,
      );
      this.error = this.convertValues(source["error"], ProjectOpenError);
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }

  export class ProjectOpenResult {
    status: string;
    root?: string;
    classification?: string;
    project?: projectlifecycle.Project;
    counts: projectlifecycle.Counts;
    snapshot?: coreadapter.Snapshot;
    diagnostics?: ApplicationDiagnostic[];
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new ProjectOpenResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.root = source["root"];
      this.classification = source["classification"];
      this.project = this.convertValues(
        source["project"],
        projectlifecycle.Project,
      );
      this.counts = this.convertValues(
        source["counts"],
        projectlifecycle.Counts,
      );
      this.snapshot = this.convertValues(
        source["snapshot"],
        coreadapter.Snapshot,
      );
      this.diagnostics = this.convertValues(
        source["diagnostics"],
        ApplicationDiagnostic,
      );
      this.error = this.convertValues(source["error"], ProjectOpenError);
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
}

export namespace projectlifecycle {
  export class CompatibilitySourceSummary {
    id: string;
    bundleDigest: string;
    catalogDigest: string;
    bundleVersion: string;

    static createFrom(source: any = {}) {
      return new CompatibilitySourceSummary(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.bundleDigest = source["bundleDigest"];
      this.catalogDigest = source["catalogDigest"];
      this.bundleVersion = source["bundleVersion"];
    }
  }
  export class Counts {
    servers: number;
    deployments: number;
    runs: number;

    static createFrom(source: any = {}) {
      return new Counts(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.servers = source["servers"];
      this.deployments = source["deployments"];
      this.runs = source["runs"];
    }
  }
  export class CreateProjectRequest {
    projectRoot: string;
    displayName: string;
    compatibilitySourceId: string;

    static createFrom(source: any = {}) {
      return new CreateProjectRequest(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.projectRoot = source["projectRoot"];
      this.displayName = source["displayName"];
      this.compatibilitySourceId = source["compatibilitySourceId"];
    }
  }
  export class Project {
    id: string;
    name: string;
    source: CompatibilitySourceSummary;

    static createFrom(source: any = {}) {
      return new Project(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.name = source["name"];
      this.source = this.convertValues(
        source["source"],
        CompatibilitySourceSummary,
      );
    }

    convertValues(a: any, classs: any, asMap: boolean = false): any {
      if (!a) {
        return a;
      }
      if (a.slice && a.map) {
        return (a as any[]).map((elem) => this.convertValues(elem, classs));
      } else if ("object" === typeof a) {
        if (asMap) {
          for (const key of Object.keys(a)) {
            a[key] = new classs(a[key]);
          }
          return a;
        }
        return new classs(a);
      }
      return a;
    }
  }
}
