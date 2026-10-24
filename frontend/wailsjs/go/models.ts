export namespace appconfig {
  export class LibraryExecutionPriority {
    libraryName: string;
    priority?: number;

    static createFrom(source: any = {}) {
      return new LibraryExecutionPriority(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.libraryName = source["libraryName"];
      this.priority = source["priority"];
    }
  }
  export class ServiceExecutionPriority {
    serviceType: string;
    priority?: number;

    static createFrom(source: any = {}) {
      return new ServiceExecutionPriority(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.serviceType = source["serviceType"];
      this.priority = source["priority"];
    }
  }
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
    serviceExecutionPriorities: ServiceExecutionPriority[];
    libraryExecutionPriorities: LibraryExecutionPriority[];

    static createFrom(source: any = {}) {
      return new Config(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.schemaVersion = source["schemaVersion"];
      this.serverTypes = this.convertValues(source["serverTypes"], ServerType);
      this.serviceExecutionPriorities = this.convertValues(
        source["serviceExecutionPriorities"],
        ServiceExecutionPriority,
      );
      this.libraryExecutionPriorities = this.convertValues(
        source["libraryExecutionPriorities"],
        LibraryExecutionPriority,
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

export namespace coreadapter {
  export class ApplicationOrigin {
    resolution: string;
    precision: string;
    applicationPackage: string;
    libraryPackage: string;
    host: string;

    static createFrom(source: any = {}) {
      return new ApplicationOrigin(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.resolution = source["resolution"];
      this.precision = source["precision"];
      this.applicationPackage = source["applicationPackage"];
      this.libraryPackage = source["libraryPackage"];
      this.host = source["host"];
    }
  }
  export class ApplicationPlacement {
    connectionSettings?: Record<string, Array<number>>;
    topicBindings: Record<string, any>;
    runtimeDirectory: string;
    commonDefaults?: Record<string, Array<number>>;
    inherited?: Record<string, Array<number>>;
    SERVER_ID: string;
    runtimeRef: string;
    command: string[];
    imageRequirement: number[];
    origin: ApplicationOrigin;
    parameters: Record<string, Array<number>>;
    environment: Record<string, any>;
    ports: Record<string, Array<number>>;
    endpoint: number[];
    containerName: string;
    composeProject: string;
    runtimePath: string;
    libraryEnvPath: string;

    static createFrom(source: any = {}) {
      return new ApplicationPlacement(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.connectionSettings = source["connectionSettings"];
      this.topicBindings = source["topicBindings"];
      this.runtimeDirectory = source["runtimeDirectory"];
      this.commonDefaults = source["commonDefaults"];
      this.inherited = source["inherited"];
      this.SERVER_ID = source["SERVER_ID"];
      this.runtimeRef = source["runtimeRef"];
      this.command = source["command"];
      this.imageRequirement = source["imageRequirement"];
      this.origin = this.convertValues(source["origin"], ApplicationOrigin);
      this.parameters = source["parameters"];
      this.environment = source["environment"];
      this.ports = source["ports"];
      this.endpoint = source["endpoint"];
      this.containerName = source["containerName"];
      this.composeProject = source["composeProject"];
      this.runtimePath = source["runtimePath"];
      this.libraryEnvPath = source["libraryEnvPath"];
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
  export class ApplicationInstance {
    topics: Record<string, Array<number>>;
    applicationName: string;
    slotId: string;
    placements: Record<string, ApplicationPlacement>;
    connections: Record<string, Array<number>>;
    credentialRequirements: Record<string, Array<number>>;
    runtimeSecretRequirements: string[];
    secretBindings: Record<string, Array<number>>;
    agentRequired: boolean;
    executionPrerequisites: string[];
    identityEnvironment: Record<string, string>;
    imageRequirement: number[];
    approle: number[];

    static createFrom(source: any = {}) {
      return new ApplicationInstance(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.topics = source["topics"];
      this.applicationName = source["applicationName"];
      this.slotId = source["slotId"];
      this.placements = this.convertValues(
        source["placements"],
        ApplicationPlacement,
        true,
      );
      this.connections = source["connections"];
      this.credentialRequirements = source["credentialRequirements"];
      this.runtimeSecretRequirements = source["runtimeSecretRequirements"];
      this.secretBindings = source["secretBindings"];
      this.agentRequired = source["agentRequired"];
      this.executionPrerequisites = source["executionPrerequisites"];
      this.identityEnvironment = source["identityEnvironment"];
      this.imageRequirement = source["imageRequirement"];
      this.approle = source["approle"];
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
  export class ApplicationLibrary {
    providedConnections?: Record<string, Array<number>>;
    registryCredentials?: Record<string, Array<number>>;
    registries?: string[];
    tables?: Record<string, Array<number>>;
    resourceDefaults?: Record<string, Array<number>>;
    topics: Record<string, Array<number>>;
    runtimeDirectory: string;
    connections: Record<string, Array<number>>;
    libraryRef: string;
    packages: Record<string, Array<number>>;
    instances: Record<string, ApplicationInstance>;
    resources: Record<string, Array<number>>;
    sharedSecretRequirements: Record<string, Array<number>>;

    static createFrom(source: any = {}) {
      return new ApplicationLibrary(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.providedConnections = source["providedConnections"];
      this.registryCredentials = source["registryCredentials"];
      this.registries = source["registries"];
      this.tables = source["tables"];
      this.resourceDefaults = source["resourceDefaults"];
      this.topics = source["topics"];
      this.runtimeDirectory = source["runtimeDirectory"];
      this.connections = source["connections"];
      this.libraryRef = source["libraryRef"];
      this.packages = source["packages"];
      this.instances = this.convertValues(
        source["instances"],
        ApplicationInstance,
        true,
      );
      this.resources = source["resources"];
      this.sharedSecretRequirements = source["sharedSecretRequirements"];
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
  export class ApplicationLibraries {
    apiVersion: string;
    status: string;
    libraries: Record<string, ApplicationLibrary>;
    findings: any[];

    static createFrom(source: any = {}) {
      return new ApplicationLibraries(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.status = source["status"];
      this.libraries = this.convertValues(
        source["libraries"],
        ApplicationLibrary,
        true,
      );
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
    apiVersion: string;
    applicationLibraries?: ApplicationLibraries;
    status: string;
    partial: boolean;
    project: Record<string, any>;
    projectRevision: string;
    snapshotFingerprint: string;
    documents: Document[];
    hosts: Record<string, any>;
    references: Record<string, any>;
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
      this.apiVersion = source["apiVersion"];
      this.applicationLibraries = this.convertValues(
        source["applicationLibraries"],
        ApplicationLibraries,
      );
      this.status = source["status"];
      this.partial = source["partial"];
      this.project = source["project"];
      this.projectRevision = source["projectRevision"];
      this.snapshotFingerprint = source["snapshotFingerprint"];
      this.documents = this.convertValues(source["documents"], Document);
      this.hosts = source["hosts"];
      this.references = source["references"];
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

export namespace desktop {
  export class ProjectOpenError {
    code: string;
    message: string;
    diagnosticCodes?: string[];

    static createFrom(source: any = {}) {
      return new ProjectOpenError(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.code = source["code"];
      this.message = source["message"];
      this.diagnosticCodes = source["diagnosticCodes"];
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
  export class VerificationFinding {
    code: string;
    severity: string;
    summary: string;
    subjectKind?: string;
    subjectId?: string;
    helpRef?: string;

    static createFrom(source: any = {}) {
      return new VerificationFinding(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.code = source["code"];
      this.severity = source["severity"];
      this.summary = source["summary"];
      this.subjectKind = source["subjectKind"];
      this.subjectId = source["subjectId"];
      this.helpRef = source["helpRef"];
    }
  }
  export class EndpointPreviewVirtualAddress {
    address: string;
    interface: string;

    static createFrom(source: any = {}) {
      return new EndpointPreviewVirtualAddress(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.address = source["address"];
      this.interface = source["interface"];
    }
  }
  export class EndpointPreviewProvider {
    endpointGroupId: string;
    providerDeploymentId: string;
    endpointGroupRef: string;
    virtualRouterId: number;
    virtualAddresses: EndpointPreviewVirtualAddress[];

    static createFrom(source: any = {}) {
      return new EndpointPreviewProvider(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.endpointGroupId = source["endpointGroupId"];
      this.providerDeploymentId = source["providerDeploymentId"];
      this.endpointGroupRef = source["endpointGroupRef"];
      this.virtualRouterId = source["virtualRouterId"];
      this.virtualAddresses = this.convertValues(
        source["virtualAddresses"],
        EndpointPreviewVirtualAddress,
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
  export class EndpointPreviewEndpoint {
    deploymentId: string;
    fqdn: string;

    static createFrom(source: any = {}) {
      return new EndpointPreviewEndpoint(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.deploymentId = source["deploymentId"];
      this.fqdn = source["fqdn"];
    }
  }
  export class EndpointPreview {
    status: string;
    endpoints?: EndpointPreviewEndpoint[];
    providers?: EndpointPreviewProvider[];
    findings?: VerificationFinding[];
    findingsTruncated?: boolean;
    truncated?: boolean;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new EndpointPreview(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.endpoints = this.convertValues(
        source["endpoints"],
        EndpointPreviewEndpoint,
      );
      this.providers = this.convertValues(
        source["providers"],
        EndpointPreviewProvider,
      );
      this.findings = this.convertValues(
        source["findings"],
        VerificationFinding,
      );
      this.findingsTruncated = source["findingsTruncated"];
      this.truncated = source["truncated"];
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

  export class ExecutionNodeContext {
    status: string;
    selectionKind: string;
    selectionSource: string;
    selectedHostId?: string;
    runtimeDigest?: string;
    safeLabel?: string;
    locked: boolean;

    static createFrom(source: any = {}) {
      return new ExecutionNodeContext(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.selectionKind = source["selectionKind"];
      this.selectionSource = source["selectionSource"];
      this.selectedHostId = source["selectedHostId"];
      this.runtimeDigest = source["runtimeDigest"];
      this.safeLabel = source["safeLabel"];
      this.locked = source["locked"];
    }
  }
  export class ProjectVerification {
    apiVersion: string;
    kind: string;
    status: string;
    projectIdentity?: string;
    projectRevision?: string;
    executionNodeId?: string;
    runtime?: executionnode.RuntimeEvidence;
    findings?: VerificationFinding[];
    findingsTruncated?: boolean;
    // Go type: time
    checkedAt?: any;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new ProjectVerification(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.status = source["status"];
      this.projectIdentity = source["projectIdentity"];
      this.projectRevision = source["projectRevision"];
      this.executionNodeId = source["executionNodeId"];
      this.runtime = this.convertValues(
        source["runtime"],
        executionnode.RuntimeEvidence,
      );
      this.findings = this.convertValues(
        source["findings"],
        VerificationFinding,
      );
      this.findingsTruncated = source["findingsTruncated"];
      this.checkedAt = this.convertValues(source["checkedAt"], null);
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
  export class ExecutionNodeSafeFinding {
    code: string;
    safeMessage: string;

    static createFrom(source: any = {}) {
      return new ExecutionNodeSafeFinding(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.code = source["code"];
      this.safeMessage = source["safeMessage"];
    }
  }
  export class ExecutionNodeSafeStep {
    id: string;
    action: string;
    mutates: boolean;

    static createFrom(source: any = {}) {
      return new ExecutionNodeSafeStep(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.action = source["action"];
      this.mutates = source["mutates"];
    }
  }
  export class ExecutionNodePreparation {
    status: string;
    planId?: string;
    expiresAt?: string;
    steps?: ExecutionNodeSafeStep[];
    findings?: ExecutionNodeSafeFinding[];
    error?: ProjectOpenError;
    verification?: ProjectVerification;

    static createFrom(source: any = {}) {
      return new ExecutionNodePreparation(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.planId = source["planId"];
      this.expiresAt = source["expiresAt"];
      this.steps = this.convertValues(source["steps"], ExecutionNodeSafeStep);
      this.findings = this.convertValues(
        source["findings"],
        ExecutionNodeSafeFinding,
      );
      this.error = this.convertValues(source["error"], ProjectOpenError);
      this.verification = this.convertValues(
        source["verification"],
        ProjectVerification,
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
  export class ExecutionNodeReadiness {
    status: string;
    nodeId?: string;
    safeLabel?: string;
    checkedAt?: string;
    findings?: ExecutionNodeSafeFinding[];
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new ExecutionNodeReadiness(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.nodeId = source["nodeId"];
      this.safeLabel = source["safeLabel"];
      this.checkedAt = source["checkedAt"];
      this.findings = this.convertValues(
        source["findings"],
        ExecutionNodeSafeFinding,
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

  export class HostKeyProbeResult {
    status: string;
    probeId?: string;
    safeLabel?: string;
    keyType?: string;
    fingerprint?: string;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new HostKeyProbeResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.probeId = source["probeId"];
      this.safeLabel = source["safeLabel"];
      this.keyType = source["keyType"];
      this.fingerprint = source["fingerprint"];
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
  export class InfrastructureVerificationView {
    availability: string;
    observedAt?: string;
    previous?: executionnode.InfrastructureVerification;

    static createFrom(source: any = {}) {
      return new InfrastructureVerificationView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.availability = source["availability"];
      this.observedAt = source["observedAt"];
      this.previous = this.convertValues(
        source["previous"],
        executionnode.InfrastructureVerification,
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
  export class InstallationAcknowledgement {
    code: string;
    summary: string;

    static createFrom(source: any = {}) {
      return new InstallationAcknowledgement(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.code = source["code"];
      this.summary = source["summary"];
    }
  }
  export class InstallationTaskView {
    role?: string;
    name?: string;
    uuid?: string;

    static createFrom(source: any = {}) {
      return new InstallationTaskView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.role = source["role"];
      this.name = source["name"];
      this.uuid = source["uuid"];
    }
  }
  export class InstallationEventView {
    runId: string;
    sequence: number;
    timestamp: string;
    eventType: string;
    status: string;
    phaseId?: string;
    actionId?: string;
    host?: string;
    serviceDeployment?: string;
    task?: InstallationTaskView;
    elapsedMilliseconds?: number;
    safeMessage: string;
    errorCode?: string;
    errorSummary?: string;
    redacted: boolean;

    static createFrom(source: any = {}) {
      return new InstallationEventView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.runId = source["runId"];
      this.sequence = source["sequence"];
      this.timestamp = source["timestamp"];
      this.eventType = source["eventType"];
      this.status = source["status"];
      this.phaseId = source["phaseId"];
      this.actionId = source["actionId"];
      this.host = source["host"];
      this.serviceDeployment = source["serviceDeployment"];
      this.task = this.convertValues(source["task"], InstallationTaskView);
      this.elapsedMilliseconds = source["elapsedMilliseconds"];
      this.safeMessage = source["safeMessage"];
      this.errorCode = source["errorCode"];
      this.errorSummary = source["errorSummary"];
      this.redacted = source["redacted"];
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
  export class InstallationNodeState {
    status: string;
    safeLabel?: string;

    static createFrom(source: any = {}) {
      return new InstallationNodeState(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.safeLabel = source["safeLabel"];
    }
  }
  export class InstallationPlanAction {
    id: string;
    type: string;
    serviceDeployment?: string;
    targets: string[];
    dependsOn: string[];
    mutating: boolean;
    reboot: string;
    summary: string;

    static createFrom(source: any = {}) {
      return new InstallationPlanAction(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.type = source["type"];
      this.serviceDeployment = source["serviceDeployment"];
      this.targets = source["targets"];
      this.dependsOn = source["dependsOn"];
      this.mutating = source["mutating"];
      this.reboot = source["reboot"];
      this.summary = source["summary"];
    }
  }
  export class InstallationPlanFinding {
    code: string;
    safeMessage: string;

    static createFrom(source: any = {}) {
      return new InstallationPlanFinding(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.code = source["code"];
      this.safeMessage = source["safeMessage"];
    }
  }
  export class InstallationPlanPhase {
    id: string;
    order: number;
    actions: InstallationPlanAction[];

    static createFrom(source: any = {}) {
      return new InstallationPlanPhase(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.order = source["order"];
      this.actions = this.convertValues(
        source["actions"],
        InstallationPlanAction,
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
  export class InstallationRuntimeBinding {
    bundleDigest: string;
    coreVersion: string;
    catalogDigest: string;
    protocol: string;

    static createFrom(source: any = {}) {
      return new InstallationRuntimeBinding(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.bundleDigest = source["bundleDigest"];
      this.coreVersion = source["coreVersion"];
      this.catalogDigest = source["catalogDigest"];
      this.protocol = source["protocol"];
    }
  }
  export class InstallationPlanView {
    skipInfrastructureVerify: boolean;
    executionMode: string;
    infrastructureVerification?: executionnode.InfrastructureVerification;
    infrastructureObservedAt?: string;
    infrastructureCacheWarning?: boolean;
    id: string;
    status: string;
    projectRevision: string;
    planFingerprint: string;
    executionNodeId: string;
    runtime: InstallationRuntimeBinding;
    expiresAt: string;
    approved: boolean;
    acknowledgements: InstallationAcknowledgement[];
    phases: InstallationPlanPhase[];
    findings?: InstallationPlanFinding[];
    pkiStorePasswordRequired: boolean;
    secretOutputEncryptionRequired: boolean;
    secretOutputEncryptionPasswordPresent: boolean;

    static createFrom(source: any = {}) {
      return new InstallationPlanView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.skipInfrastructureVerify = source["skipInfrastructureVerify"];
      this.executionMode = source["executionMode"];
      this.infrastructureVerification = this.convertValues(
        source["infrastructureVerification"],
        executionnode.InfrastructureVerification,
      );
      this.infrastructureObservedAt = source["infrastructureObservedAt"];
      this.infrastructureCacheWarning = source["infrastructureCacheWarning"];
      this.id = source["id"];
      this.status = source["status"];
      this.projectRevision = source["projectRevision"];
      this.planFingerprint = source["planFingerprint"];
      this.executionNodeId = source["executionNodeId"];
      this.runtime = this.convertValues(
        source["runtime"],
        InstallationRuntimeBinding,
      );
      this.expiresAt = source["expiresAt"];
      this.approved = source["approved"];
      this.acknowledgements = this.convertValues(
        source["acknowledgements"],
        InstallationAcknowledgement,
      );
      this.phases = this.convertValues(source["phases"], InstallationPlanPhase);
      this.findings = this.convertValues(
        source["findings"],
        InstallationPlanFinding,
      );
      this.pkiStorePasswordRequired = source["pkiStorePasswordRequired"];
      this.secretOutputEncryptionRequired =
        source["secretOutputEncryptionRequired"];
      this.secretOutputEncryptionPasswordPresent =
        source["secretOutputEncryptionPasswordPresent"];
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
  export class InstallationPlanOperation {
    status: string;
    plan?: InstallationPlanView;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new InstallationPlanOperation(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.plan = this.convertValues(source["plan"], InstallationPlanView);
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

  export class InstallationPlanRequest {
    skipInfrastructureVerify: boolean;
    executionMode: string;
    deploymentOrder: string[];
    applicationLibraryOrder: string[];
    applicationVaultSources: Record<string, string>;

    static createFrom(source: any = {}) {
      return new InstallationPlanRequest(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.skipInfrastructureVerify = source["skipInfrastructureVerify"];
      this.executionMode = source["executionMode"];
      this.deploymentOrder = source["deploymentOrder"];
      this.applicationLibraryOrder = source["applicationLibraryOrder"];
      this.applicationVaultSources = source["applicationVaultSources"];
    }
  }
  export class InstallationPlanState {
    status: string;
    planId?: string;

    static createFrom(source: any = {}) {
      return new InstallationPlanState(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.planId = source["planId"];
    }
  }

  export class InstallationPrerequisite {
    code: string;
    destination: string;
    safeMessage: string;

    static createFrom(source: any = {}) {
      return new InstallationPrerequisite(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.code = source["code"];
      this.destination = source["destination"];
      this.safeMessage = source["safeMessage"];
    }
  }
  export class InstallationProjectState {
    id: string;
    revision: string;
    verificationStatus: string;
    hasUnsavedChanges: boolean;

    static createFrom(source: any = {}) {
      return new InstallationProjectState(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.revision = source["revision"];
      this.verificationStatus = source["verificationStatus"];
      this.hasUnsavedChanges = source["hasUnsavedChanges"];
    }
  }
  export class InstallationResultView {
    runId: string;
    state: string;
    sequence: number;

    static createFrom(source: any = {}) {
      return new InstallationResultView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.runId = source["runId"];
      this.state = source["state"];
      this.sequence = source["sequence"];
    }
  }
  export class InstallationRunView {
    runId: string;
    state: string;
    sequence: number;

    static createFrom(source: any = {}) {
      return new InstallationRunView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.runId = source["runId"];
      this.state = source["state"];
      this.sequence = source["sequence"];
    }
  }
  export class InstallationRunOperation {
    reconnected?: boolean;
    cancelUnconfirmed?: boolean;
    projectRevision?: string;
    status: string;
    run?: InstallationRunView;
    result?: InstallationResultView;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new InstallationRunOperation(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.reconnected = source["reconnected"];
      this.cancelUnconfirmed = source["cancelUnconfirmed"];
      this.projectRevision = source["projectRevision"];
      this.status = source["status"];
      this.run = this.convertValues(source["run"], InstallationRunView);
      this.result = this.convertValues(
        source["result"],
        InstallationResultView,
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

  export class InstallationState {
    apiVersion: string;
    kind: string;
    status: string;
    project?: InstallationProjectState;
    executionNode: InstallationNodeState;
    plan: InstallationPlanState;
    prerequisites?: InstallationPrerequisite[];

    static createFrom(source: any = {}) {
      return new InstallationState(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.status = source["status"];
      this.project = this.convertValues(
        source["project"],
        InstallationProjectState,
      );
      this.executionNode = this.convertValues(
        source["executionNode"],
        InstallationNodeState,
      );
      this.plan = this.convertValues(source["plan"], InstallationPlanState);
      this.prerequisites = this.convertValues(
        source["prerequisites"],
        InstallationPrerequisite,
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
  export class InstallationSubscriptionEvent {
    subscriptionId: string;
    event?: InstallationEventView;
    errorCode?: string;

    static createFrom(source: any = {}) {
      return new InstallationSubscriptionEvent(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.subscriptionId = source["subscriptionId"];
      this.event = this.convertValues(source["event"], InstallationEventView);
      this.errorCode = source["errorCode"];
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
  export class InstallationSubscriptionResult {
    status: string;
    subscriptionId?: string;
    event?: InstallationSubscriptionEvent;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new InstallationSubscriptionResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.subscriptionId = source["subscriptionId"];
      this.event = this.convertValues(
        source["event"],
        InstallationSubscriptionEvent,
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

  export class OrphanRunRecoveryResult {
    status: string;
    recoveryId?: string;
    runId?: string;
    runState?: string;
    projectRevision?: string;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new OrphanRunRecoveryResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.recoveryId = source["recoveryId"];
      this.runId = source["runId"];
      this.runState = source["runState"];
      this.projectRevision = source["projectRevision"];
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
  export class OutputEncryptionPasswordInput {
    password: string;
    confirm: string;

    static createFrom(source: any = {}) {
      return new OutputEncryptionPasswordInput(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.password = source["password"];
      this.confirm = source["confirm"];
    }
  }
  export class PendingRuntimeSecretFileInput {
    serviceDeployment: string;
    purpose: string;
    encryptionPassword: string;

    static createFrom(source: any = {}) {
      return new PendingRuntimeSecretFileInput(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.serviceDeployment = source["serviceDeployment"];
      this.purpose = source["purpose"];
      this.encryptionPassword = source["encryptionPassword"];
    }
  }
  export class PendingRuntimeSecretValuesInput {
    serviceDeployment: string;
    values: Record<string, string>;

    static createFrom(source: any = {}) {
      return new PendingRuntimeSecretValuesInput(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.serviceDeployment = source["serviceDeployment"];
      this.values = source["values"];
    }
  }
  export class ProjectExportOperationResult {
    status: string;
    plan?: installer.ProjectExportPlan;
    result?: installer.ProjectExportResult;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new ProjectExportOperationResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.plan = this.convertValues(
        source["plan"],
        installer.ProjectExportPlan,
      );
      this.result = this.convertValues(
        source["result"],
        installer.ProjectExportResult,
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
    catalog?: projectlifecycle.ProjectCatalogView;
    snapshot?: coreadapter.Snapshot;
    managed?: installer.ManagedProjectView;
    verification: ProjectVerification;
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
      this.catalog = this.convertValues(
        source["catalog"],
        projectlifecycle.ProjectCatalogView,
      );
      this.snapshot = this.convertValues(
        source["snapshot"],
        coreadapter.Snapshot,
      );
      this.managed = this.convertValues(
        source["managed"],
        installer.ManagedProjectView,
      );
      this.verification = this.convertValues(
        source["verification"],
        ProjectVerification,
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

  export class RuntimeBundleUpdateResult {
    status: string;
    previewId?: string;
    currentArtifactDigest?: string;
    currentCatalogDigest?: string;
    newArtifactDigest?: string;
    newCatalogDigest?: string;
    bundleVersion?: string;
    coreVersion?: string;
    projectRevision?: string;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new RuntimeBundleUpdateResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.previewId = source["previewId"];
      this.currentArtifactDigest = source["currentArtifactDigest"];
      this.currentCatalogDigest = source["currentCatalogDigest"];
      this.newArtifactDigest = source["newArtifactDigest"];
      this.newCatalogDigest = source["newCatalogDigest"];
      this.bundleVersion = source["bundleVersion"];
      this.coreVersion = source["coreVersion"];
      this.projectRevision = source["projectRevision"];
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
  export class RuntimeSecretDescriptorView {
    deploymentBound?: boolean;
    requirementRef: string;
    purpose: string;
    serviceDeployment?: string;
    setting?: string;
    displayLabel: string;
    requiredWhen?: string;
    operations?: string[];
    referenceConfigured: boolean;
    hosts: string[];

    static createFrom(source: any = {}) {
      return new RuntimeSecretDescriptorView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.deploymentBound = source["deploymentBound"];
      this.requirementRef = source["requirementRef"];
      this.purpose = source["purpose"];
      this.serviceDeployment = source["serviceDeployment"];
      this.setting = source["setting"];
      this.displayLabel = source["displayLabel"];
      this.requiredWhen = source["requiredWhen"];
      this.operations = source["operations"];
      this.referenceConfigured = source["referenceConfigured"];
      this.hosts = source["hosts"];
    }
  }
  export class RuntimeSecretDescriptorOperation {
    applicationSecretAvailability?: Record<string, boolean>;
    secretsInstalled?: boolean;
    status: string;
    projectRevision?: string;
    descriptorSetFingerprint?: string;
    descriptors?: RuntimeSecretDescriptorView[];
    applicationInputs?: executionnode.ApplicationSecretDescriptor[];
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new RuntimeSecretDescriptorOperation(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.applicationSecretAvailability =
        source["applicationSecretAvailability"];
      this.secretsInstalled = source["secretsInstalled"];
      this.status = source["status"];
      this.projectRevision = source["projectRevision"];
      this.descriptorSetFingerprint = source["descriptorSetFingerprint"];
      this.descriptors = this.convertValues(
        source["descriptors"],
        RuntimeSecretDescriptorView,
      );
      this.applicationInputs = this.convertValues(
        source["applicationInputs"],
        executionnode.ApplicationSecretDescriptor,
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

  export class RuntimeSecretValuesInput {
    projectRevision: string;
    descriptorSetFingerprint: string;
    serviceDeployment: string;
    applicationLibrary?: string;
    applicationRequirementRef?: string;
    values: Record<string, string>;

    static createFrom(source: any = {}) {
      return new RuntimeSecretValuesInput(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.projectRevision = source["projectRevision"];
      this.descriptorSetFingerprint = source["descriptorSetFingerprint"];
      this.serviceDeployment = source["serviceDeployment"];
      this.applicationLibrary = source["applicationLibrary"];
      this.applicationRequirementRef = source["applicationRequirementRef"];
      this.values = source["values"];
    }
  }
  export class SecretOutputDeliveryInput {
    packageId: string;

    static createFrom(source: any = {}) {
      return new SecretOutputDeliveryInput(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.packageId = source["packageId"];
    }
  }
  export class SecretOutputDeliveryOperation {
    status: string;
    package?: executionnode.SecretOutputPackage;
    directory?: string;
    stagingPath?: string;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new SecretOutputDeliveryOperation(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.package = this.convertValues(
        source["package"],
        executionnode.SecretOutputPackage,
      );
      this.directory = source["directory"];
      this.stagingPath = source["stagingPath"];
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
  export class SecretOutputPackagesOperation {
    status: string;
    packages?: executionnode.SecretOutputPackage[];
    nextCursor?: string;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new SecretOutputPackagesOperation(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.packages = this.convertValues(
        source["packages"],
        executionnode.SecretOutputPackage,
      );
      this.nextCursor = source["nextCursor"];
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
  export class ServerInformationResult {
    status: string;
    hostId?: string;
    information?: executionnode.ServerInformation;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new ServerInformationResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.hostId = source["hostId"];
      this.information = this.convertValues(
        source["information"],
        executionnode.ServerInformation,
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
  export class StructuralEditOperationResult {
    status: string;
    session?: installer.EditSession;
    plan?: installer.StructuralEditPlan;
    commit?: installer.StructuralSaveResult;
    current?: ProjectOpenResult;
    diagnostics?: ApplicationDiagnostic[];
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new StructuralEditOperationResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.session = this.convertValues(
        source["session"],
        installer.EditSession,
      );
      this.plan = this.convertValues(
        source["plan"],
        installer.StructuralEditPlan,
      );
      this.commit = this.convertValues(
        source["commit"],
        installer.StructuralSaveResult,
      );
      this.current = this.convertValues(source["current"], ProjectOpenResult);
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

  export class VerifiedPKIConsumer {
    deploymentId: string;
    memberId: string;
    hostId: string;

    static createFrom(source: any = {}) {
      return new VerifiedPKIConsumer(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.deploymentId = source["deploymentId"];
      this.memberId = source["memberId"];
      this.hostId = source["hostId"];
    }
  }
  export class VerifiedCertificateIdentity {
    id: string;
    scope: string;
    tlsProfileId: string;
    dnsNames: string[];
    ipAddresses: string[];
    consumers: VerifiedPKIConsumer[];

    static createFrom(source: any = {}) {
      return new VerifiedCertificateIdentity(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.scope = source["scope"];
      this.tlsProfileId = source["tlsProfileId"];
      this.dnsNames = source["dnsNames"];
      this.ipAddresses = source["ipAddresses"];
      this.consumers = this.convertValues(
        source["consumers"],
        VerifiedPKIConsumer,
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

  export class VerifiedPKIView {
    status: string;
    identities?: VerifiedCertificateIdentity[];
    findings?: VerificationFinding[];
    findingsTruncated?: boolean;
    error?: ProjectOpenError;

    static createFrom(source: any = {}) {
      return new VerifiedPKIView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.identities = this.convertValues(
        source["identities"],
        VerifiedCertificateIdentity,
      );
      this.findings = this.convertValues(
        source["findings"],
        VerificationFinding,
      );
      this.findingsTruncated = source["findingsTruncated"];
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

export namespace executionnode {
  export class ApplicationSecretDescriptor {
    requirementRef: string;
    purpose: string;
    providerDeployment?: string;
    applicationLibraries: string[];
    hosts: string[];
    operations: string[];
    sourceRef: string;
    displayLabel: string;

    static createFrom(source: any = {}) {
      return new ApplicationSecretDescriptor(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.requirementRef = source["requirementRef"];
      this.purpose = source["purpose"];
      this.providerDeployment = source["providerDeployment"];
      this.applicationLibraries = source["applicationLibraries"];
      this.hosts = source["hosts"];
      this.operations = source["operations"];
      this.sourceRef = source["sourceRef"];
      this.displayLabel = source["displayLabel"];
    }
  }
  export class InfrastructureDeploymentVerification {
    deploymentId: string;
    sourceRunId: string;
    coverageDigest: string;
    verifiedAt: string;

    static createFrom(source: any = {}) {
      return new InfrastructureDeploymentVerification(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.deploymentId = source["deploymentId"];
      this.sourceRunId = source["sourceRunId"];
      this.coverageDigest = source["coverageDigest"];
      this.verifiedAt = source["verifiedAt"];
    }
  }
  export class InfrastructureVerification {
    status: string;
    code?: string;
    infrastructureFingerprint?: string;
    evidenceRevision?: string;
    deployments: InfrastructureDeploymentVerification[];

    static createFrom(source: any = {}) {
      return new InfrastructureVerification(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.code = source["code"];
      this.infrastructureFingerprint = source["infrastructureFingerprint"];
      this.evidenceRevision = source["evidenceRevision"];
      this.deployments = this.convertValues(
        source["deployments"],
        InfrastructureDeploymentVerification,
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
  export class RuntimeEvidence {
    bundleDigest: string;
    coreVersion: string;
    catalogDigest: string;
    protocol: string;

    static createFrom(source: any = {}) {
      return new RuntimeEvidence(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.bundleDigest = source["bundleDigest"];
      this.coreVersion = source["coreVersion"];
      this.catalogDigest = source["catalogDigest"];
      this.protocol = source["protocol"];
    }
  }
  export class SecretOutputPackage {
    protocol: string;
    packageId: string;
    projectId: string;
    deploymentId: string;
    sourceRunId: string;
    runtimeDigest: string;
    generation: number;
    state: string;
    entries: string[];

    static createFrom(source: any = {}) {
      return new SecretOutputPackage(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.protocol = source["protocol"];
      this.packageId = source["packageId"];
      this.projectId = source["projectId"];
      this.deploymentId = source["deploymentId"];
      this.sourceRunId = source["sourceRunId"];
      this.runtimeDigest = source["runtimeDigest"];
      this.generation = source["generation"];
      this.state = source["state"];
      this.entries = source["entries"];
    }
  }
  export class ServerInformation {
    hostname: string;
    os: string;
    osVersion: string;
    architecture: string;
    cpuCount: number;
    memoryBytes: number;
    serverTime: string;
    checkedAt: string;

    static createFrom(source: any = {}) {
      return new ServerInformation(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.hostname = source["hostname"];
      this.os = source["os"];
      this.osVersion = source["osVersion"];
      this.architecture = source["architecture"];
      this.cpuCount = source["cpuCount"];
      this.memoryBytes = source["memoryBytes"];
      this.serverTime = source["serverTime"];
      this.checkedAt = source["checkedAt"];
    }
  }
  export class ServiceConfigurationValue {
    state: string;
    source: string;
    value?: any;

    static createFrom(source: any = {}) {
      return new ServiceConfigurationValue(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.state = source["state"];
      this.source = source["source"];
      this.value = source["value"];
    }
  }
  export class ServiceConfigurationScope {
    configuration: Record<string, ServiceConfigurationValue>;
    members: Record<string, any>;

    static createFrom(source: any = {}) {
      return new ServiceConfigurationScope(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.configuration = this.convertValues(
        source["configuration"],
        ServiceConfigurationValue,
        true,
      );
      this.members = source["members"];
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
  export class ServiceConfigurationPreview {
    apiVersion: string;
    kind: string;
    projectRevision: string;
    services: Record<string, ServiceConfigurationScope>;
    runtimeDigest?: string;

    static createFrom(source: any = {}) {
      return new ServiceConfigurationPreview(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.projectRevision = source["projectRevision"];
      this.services = this.convertValues(
        source["services"],
        ServiceConfigurationScope,
        true,
      );
      this.runtimeDigest = source["runtimeDigest"];
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

  export class VirtualAddress {
    address: string;
    interface: string;

    static createFrom(source: any = {}) {
      return new VirtualAddress(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.address = source["address"];
      this.interface = source["interface"];
    }
  }
  export class PlacementHost {
    hostId: string;
    roles?: string[];
    priority?: number;

    static createFrom(source: any = {}) {
      return new PlacementHost(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.hostId = source["hostId"];
      this.roles = source["roles"];
      this.priority = source["priority"];
    }
  }
  export class PlacementMember {
    memberId: string;
    hostId: string;
    roles?: string[];
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
    scope?: string;
    memberId?: string;
    setting?: string;
    value?: any;
    endpointGroupId?: string;
    haproxyDeploymentId?: string;
    hostId?: string;
    type?: string;
    desiredHostname?: string;
    address?: string;
    sshPort?: number;
    clearSSHPort?: boolean;
    serviceType?: string;
    mode?: string;
    entityId?: string;
    entity?: Record<string, any>;
    members?: PlacementMember[];
    hosts?: PlacementHost[];
    property?: string;
    deployment?: Record<string, any>;
    endpointGroup?: Record<string, any>;
    virtualRouterId?: number;
    virtualAddresses?: VirtualAddress[];
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
      this.scope = source["scope"];
      this.memberId = source["memberId"];
      this.setting = source["setting"];
      this.value = source["value"];
      this.endpointGroupId = source["endpointGroupId"];
      this.haproxyDeploymentId = source["haproxyDeploymentId"];
      this.hostId = source["hostId"];
      this.type = source["type"];
      this.desiredHostname = source["desiredHostname"];
      this.address = source["address"];
      this.sshPort = source["sshPort"];
      this.clearSSHPort = source["clearSSHPort"];
      this.serviceType = source["serviceType"];
      this.mode = source["mode"];
      this.entityId = source["entityId"];
      this.entity = source["entity"];
      this.members = this.convertValues(source["members"], PlacementMember);
      this.hosts = this.convertValues(source["hosts"], PlacementHost);
      this.property = source["property"];
      this.deployment = source["deployment"];
      this.endpointGroup = source["endpointGroup"];
      this.virtualRouterId = source["virtualRouterId"];
      this.virtualAddresses = this.convertValues(
        source["virtualAddresses"],
        VirtualAddress,
      );
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
  export class ManagedPKI {
    authorities: Record<string, any>;
    profiles: Record<string, any>;
    tlsProfiles: Record<string, any>;
    scopes: Record<string, any>;

    static createFrom(source: any = {}) {
      return new ManagedPKI(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.authorities = source["authorities"];
      this.profiles = source["profiles"];
      this.tlsProfiles = source["tlsProfiles"];
      this.scopes = source["scopes"];
    }
  }
  export class ManagedHostPlacement {
    deploymentId: string;
    hostId: string;
    roles: string[];
    priority?: number;

    static createFrom(source: any = {}) {
      return new ManagedHostPlacement(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.deploymentId = source["deploymentId"];
      this.hostId = source["hostId"];
      this.roles = source["roles"];
      this.priority = source["priority"];
    }
  }
  export class ManagedMemberPlacement {
    deploymentId: string;
    memberId: string;
    hostId: string;
    roles: string[];
    configuration: ManagedConfigurationOverride[];

    static createFrom(source: any = {}) {
      return new ManagedMemberPlacement(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.deploymentId = source["deploymentId"];
      this.memberId = source["memberId"];
      this.hostId = source["hostId"];
      this.roles = source["roles"];
      this.configuration = this.convertValues(
        source["configuration"],
        ManagedConfigurationOverride,
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
  export class ManagedEndpointGroup {
    endpointGroupId: string;
    domain: string;
    wildcard: boolean;

    static createFrom(source: any = {}) {
      return new ManagedEndpointGroup(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.endpointGroupId = source["endpointGroupId"];
      this.domain = source["domain"];
      this.wildcard = source["wildcard"];
    }
  }
  export class ManagedConfigurationOverride {
    setting: string;
    overridePresent: boolean;
    state: string;
    value?: any;

    static createFrom(source: any = {}) {
      return new ManagedConfigurationOverride(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.setting = source["setting"];
      this.overridePresent = source["overridePresent"];
      this.state = source["state"];
      this.value = source["value"];
    }
  }
  export class ManagedDeployment {
    deploymentId: string;
    serviceType: string;
    mode: string;
    endpointGroup?: string;
    endpointGroupRef?: string;
    virtualRouterId?: number;
    virtualAddresses?: VirtualAddress[];
    providerEditState: string;
    configuration: ManagedConfigurationOverride[];

    static createFrom(source: any = {}) {
      return new ManagedDeployment(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.deploymentId = source["deploymentId"];
      this.serviceType = source["serviceType"];
      this.mode = source["mode"];
      this.endpointGroup = source["endpointGroup"];
      this.endpointGroupRef = source["endpointGroupRef"];
      this.virtualRouterId = source["virtualRouterId"];
      this.virtualAddresses = this.convertValues(
        source["virtualAddresses"],
        VirtualAddress,
      );
      this.providerEditState = source["providerEditState"];
      this.configuration = this.convertValues(
        source["configuration"],
        ManagedConfigurationOverride,
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
  export class ManagedServer {
    hostId: string;
    type?: string;
    desiredHostname?: string;
    address?: string;
    sshPort?: number;

    static createFrom(source: any = {}) {
      return new ManagedServer(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.hostId = source["hostId"];
      this.type = source["type"];
      this.desiredHostname = source["desiredHostname"];
      this.address = source["address"];
      this.sshPort = source["sshPort"];
    }
  }
  export class ManagedApplicationPackage {
    kind: string;
    ref: string;
    digest: string;
    definition: Record<string, any>;

    static createFrom(source: any = {}) {
      return new ManagedApplicationPackage(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.kind = source["kind"];
      this.ref = source["ref"];
      this.digest = source["digest"];
      this.definition = source["definition"];
    }
  }
  export class ManagedProjectView {
    applicationPackages: Record<string, ManagedApplicationPackage>;
    applicationLibraries: Record<string, any>;
    applicationPlacements: Record<string, any>;
    projectRevision: string;
    dataRootDirectory: string;
    namePrefix: string;
    servers: Record<string, ManagedServer>;
    deployments: Record<string, ManagedDeployment>;
    endpointGroups: Record<string, ManagedEndpointGroup>;
    memberPlacements: ManagedMemberPlacement[];
    hostPlacements: ManagedHostPlacement[];
    pki: ManagedPKI;

    static createFrom(source: any = {}) {
      return new ManagedProjectView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.applicationPackages = this.convertValues(
        source["applicationPackages"],
        ManagedApplicationPackage,
        true,
      );
      this.applicationLibraries = source["applicationLibraries"];
      this.applicationPlacements = source["applicationPlacements"];
      this.projectRevision = source["projectRevision"];
      this.dataRootDirectory = source["dataRootDirectory"];
      this.namePrefix = source["namePrefix"];
      this.servers = this.convertValues(source["servers"], ManagedServer, true);
      this.deployments = this.convertValues(
        source["deployments"],
        ManagedDeployment,
        true,
      );
      this.endpointGroups = this.convertValues(
        source["endpointGroups"],
        ManagedEndpointGroup,
        true,
      );
      this.memberPlacements = this.convertValues(
        source["memberPlacements"],
        ManagedMemberPlacement,
      );
      this.hostPlacements = this.convertValues(
        source["hostPlacements"],
        ManagedHostPlacement,
      );
      this.pki = this.convertValues(source["pki"], ManagedPKI);
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
    managed?: ManagedProjectView;
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
      this.managed = this.convertValues(source["managed"], ManagedProjectView);
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

  export class ProjectExportDocument {
    logicalPath: string;
    size: number;
    digest: string;

    static createFrom(source: any = {}) {
      return new ProjectExportDocument(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.logicalPath = source["logicalPath"];
      this.size = source["size"];
      this.digest = source["digest"];
    }
  }
  export class ProjectExportPlan {
    apiVersion: string;
    kind: string;
    sourceProjectRoot: string;
    sourceProjectRevision: string;
    destinationParent: string;
    directoryName: string;
    destinationRoot: string;
    documents: ProjectExportDocument[];
    aggregateSize: number;
    excludedCategories: string[];
    planDigest: string;

    static createFrom(source: any = {}) {
      return new ProjectExportPlan(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.sourceProjectRoot = source["sourceProjectRoot"];
      this.sourceProjectRevision = source["sourceProjectRevision"];
      this.destinationParent = source["destinationParent"];
      this.directoryName = source["directoryName"];
      this.destinationRoot = source["destinationRoot"];
      this.documents = this.convertValues(
        source["documents"],
        ProjectExportDocument,
      );
      this.aggregateSize = source["aggregateSize"];
      this.excludedCategories = source["excludedCategories"];
      this.planDigest = source["planDigest"];
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
  export class ProjectExportResult {
    apiVersion: string;
    kind: string;
    status: string;
    destinationRoot?: string;
    sourceProjectRevision?: string;
    documentCount: number;
    aggregateSize: number;
    errorCode?: string;

    static createFrom(source: any = {}) {
      return new ProjectExportResult(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.status = source["status"];
      this.destinationRoot = source["destinationRoot"];
      this.sourceProjectRevision = source["sourceProjectRevision"];
      this.documentCount = source["documentCount"];
      this.aggregateSize = source["aggregateSize"];
      this.errorCode = source["errorCode"];
    }
  }

  export class StructuralEditPlan {
    apiVersion: string;
    kind: string;
    status: string;
    finding?: Finding;
    planId?: string;
    baseProjectRevision: string;
    semanticChanges: SemanticChange[];
    affectedEntities: string[];
    affectedDocuments: DocumentChange[];
    reviewDiff: string;
    saveAllowed: boolean;
    // Go type: time
    expiresAt?: any;

    static createFrom(source: any = {}) {
      return new StructuralEditPlan(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.apiVersion = source["apiVersion"];
      this.kind = source["kind"];
      this.status = source["status"];
      this.finding = this.convertValues(source["finding"], Finding);
      this.planId = source["planId"];
      this.baseProjectRevision = source["baseProjectRevision"];
      this.semanticChanges = this.convertValues(
        source["semanticChanges"],
        SemanticChange,
      );
      this.affectedEntities = source["affectedEntities"];
      this.affectedDocuments = this.convertValues(
        source["affectedDocuments"],
        DocumentChange,
      );
      this.reviewDiff = source["reviewDiff"];
      this.saveAllowed = source["saveAllowed"];
      this.expiresAt = this.convertValues(source["expiresAt"], null);
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
  export class StructuralSaveResult {
    apiVersion: string;
    kind: string;
    status: string;
    changed: boolean;
    finding?: Finding;
    oldProjectRevision?: string;
    newProjectRevision?: string;
    affectedDocuments?: DocumentChange[];
    timing: CommitTiming;
    managed?: ManagedProjectView;

    static createFrom(source: any = {}) {
      return new StructuralSaveResult(source);
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
      this.timing = this.convertValues(source["timing"], CommitTiming);
      this.managed = this.convertValues(source["managed"], ManagedProjectView);
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
  export class CatalogViewError {
    code: string;
    message: string;

    static createFrom(source: any = {}) {
      return new CatalogViewError(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.code = source["code"];
      this.message = source["message"];
    }
  }
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
  export class ProjectCatalogRoleCardinality {
    role: string;
    minimum: number;
    maximum?: number;

    static createFrom(source: any = {}) {
      return new ProjectCatalogRoleCardinality(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.role = source["role"];
      this.minimum = source["minimum"];
      this.maximum = source["maximum"];
    }
  }
  export class ProjectCatalogModeGuidance {
    minParticipants: number;
    maxParticipants?: number;
    distinctHosts: boolean;
    roleCardinality?: ProjectCatalogRoleCardinality[];

    static createFrom(source: any = {}) {
      return new ProjectCatalogModeGuidance(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.minParticipants = source["minParticipants"];
      this.maxParticipants = source["maxParticipants"];
      this.distinctHosts = source["distinctHosts"];
      this.roleCardinality = this.convertValues(
        source["roleCardinality"],
        ProjectCatalogRoleCardinality,
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
  export class ProjectCatalogMode {
    id: string;
    displayName: string;
    description?: string;
    placementKind: string;
    roles: string[];
    requiredRuntimeSecretSettings?: string[];
    guidance: ProjectCatalogModeGuidance;

    static createFrom(source: any = {}) {
      return new ProjectCatalogMode(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.displayName = source["displayName"];
      this.description = source["description"];
      this.placementKind = source["placementKind"];
      this.roles = source["roles"];
      this.requiredRuntimeSecretSettings =
        source["requiredRuntimeSecretSettings"];
      this.guidance = this.convertValues(
        source["guidance"],
        ProjectCatalogModeGuidance,
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

  export class ProjectCatalogSecretInput {
    requirementRef: string;
    purpose: string;
    displayLabel: string;
    requiredWhen: string;
    operations: string[];

    static createFrom(source: any = {}) {
      return new ProjectCatalogSecretInput(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.requirementRef = source["requirementRef"];
      this.purpose = source["purpose"];
      this.displayLabel = source["displayLabel"];
      this.requiredWhen = source["requiredWhen"];
      this.operations = source["operations"];
    }
  }
  export class ProjectCatalogSetting {
    id: string;
    kind: string;
    scopes: string[];
    label?: string;
    description?: string;
    section?: string;
    order?: number;
    editorShape: string;
    referenceKind?: string;
    runtimeSecretRequirementRef?: string;
    runtimeSecretUsernameRequired?: boolean;
    runtimeSecretDeploymentBound?: boolean;
    minimum?: number;
    maximum?: number;
    minLength?: number;
    maxLength?: number;
    enum?: any[];
    staticDefaultState?: string;
    staticDefaultValue?: any;

    static createFrom(source: any = {}) {
      return new ProjectCatalogSetting(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.kind = source["kind"];
      this.scopes = source["scopes"];
      this.label = source["label"];
      this.description = source["description"];
      this.section = source["section"];
      this.order = source["order"];
      this.editorShape = source["editorShape"];
      this.referenceKind = source["referenceKind"];
      this.runtimeSecretRequirementRef = source["runtimeSecretRequirementRef"];
      this.runtimeSecretUsernameRequired =
        source["runtimeSecretUsernameRequired"];
      this.runtimeSecretDeploymentBound =
        source["runtimeSecretDeploymentBound"];
      this.minimum = source["minimum"];
      this.maximum = source["maximum"];
      this.minLength = source["minLength"];
      this.maxLength = source["maxLength"];
      this.enum = source["enum"];
      this.staticDefaultState = source["staticDefaultState"];
      this.staticDefaultValue = source["staticDefaultValue"];
    }
  }
  export class ProjectCatalogUI {
    icon?: string;
    order?: number;
    documentationTopic?: string;

    static createFrom(source: any = {}) {
      return new ProjectCatalogUI(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.icon = source["icon"];
      this.order = source["order"];
      this.documentationTopic = source["documentationTopic"];
    }
  }
  export class ProjectCatalogService {
    id: string;
    definitionVersion: string;
    displayName: string;
    description?: string;
    category?: string;
    ui: ProjectCatalogUI;
    endpointConsumer: boolean;
    endpointProvider: boolean;
    modes: ProjectCatalogMode[];
    configurationSettings: ProjectCatalogSetting[];
    secretInputs?: ProjectCatalogSecretInput[];
    secretOutputEntries?: string[];

    static createFrom(source: any = {}) {
      return new ProjectCatalogService(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.id = source["id"];
      this.definitionVersion = source["definitionVersion"];
      this.displayName = source["displayName"];
      this.description = source["description"];
      this.category = source["category"];
      this.ui = this.convertValues(source["ui"], ProjectCatalogUI);
      this.endpointConsumer = source["endpointConsumer"];
      this.endpointProvider = source["endpointProvider"];
      this.modes = this.convertValues(source["modes"], ProjectCatalogMode);
      this.configurationSettings = this.convertValues(
        source["configurationSettings"],
        ProjectCatalogSetting,
      );
      this.secretInputs = this.convertValues(
        source["secretInputs"],
        ProjectCatalogSecretInput,
      );
      this.secretOutputEntries = source["secretOutputEntries"];
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

  export class ProjectCatalogView {
    status: string;
    expectedBundleDigest: string;
    expectedCatalogDigest: string;
    bundleVersion?: string;
    services?: ProjectCatalogService[];
    error?: CatalogViewError;

    static createFrom(source: any = {}) {
      return new ProjectCatalogView(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.expectedBundleDigest = source["expectedBundleDigest"];
      this.expectedCatalogDigest = source["expectedCatalogDigest"];
      this.bundleVersion = source["bundleVersion"];
      this.services = this.convertValues(
        source["services"],
        ProjectCatalogService,
      );
      this.error = this.convertValues(source["error"], CatalogViewError);
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

export namespace runtimesecret {
  export class Input {
    username: string;
    sshMode: string;
    sshPassword: string;
    privateKeyPath: string;
    elevationMode: string;
    elevationPassword: string;

    static createFrom(source: any = {}) {
      return new Input(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.username = source["username"];
      this.sshMode = source["sshMode"];
      this.sshPassword = source["sshPassword"];
      this.privateKeyPath = source["privateKeyPath"];
      this.elevationMode = source["elevationMode"];
      this.elevationPassword = source["elevationPassword"];
    }
  }
  export class Status {
    status: string;
    username?: string;
    sshMode?: string;
    sudoPasswordStatus: string;
    pkiStorePasswordStatus: string;
    expiresAt?: string;

    static createFrom(source: any = {}) {
      return new Status(source);
    }

    constructor(source: any = {}) {
      if ("string" === typeof source) source = JSON.parse(source);
      this.status = source["status"];
      this.username = source["username"];
      this.sshMode = source["sshMode"];
      this.sudoPasswordStatus = source["sudoPasswordStatus"];
      this.pkiStorePasswordStatus = source["pkiStorePasswordStatus"];
      this.expiresAt = source["expiresAt"];
    }
  }
}
