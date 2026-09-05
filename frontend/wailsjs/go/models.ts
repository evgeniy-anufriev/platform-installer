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
  export class ProjectOpenResult {
    status: string;
    root?: string;
    classification?: string;
    project?: projectlifecycle.Project;
    counts: projectlifecycle.Counts;
    snapshot?: coreadapter.Snapshot;
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
