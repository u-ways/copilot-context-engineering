---
name: secure-development-and-dependency-scanning
title: "Secure development and dependency scanning"
description: "Handle application-security work inside code and build: secure design and coding controls, dependency and SBOM vulnerability scanning, CVE suppression, code smells, and governance as a side effect."
---

Apply this procedure to security work that lives inside the codebase and the build rather than in the hosting platform. `practices/security.md` is the overall control set; `tools/dependency-scan/README.md` and `tools/dependency-check-maven/README.md` describe dependency and SBOM scanning, including how to suppress a CVE that does not apply; `tools/sonarqube.md` covers code-level findings and smells. `patterns/governance-side-effect.md` explains why the evidence governance needs should fall out of the pipeline rather than be produced by hand.

#### Reference: practices/security.md

<!-- cce:include practices/security.md -->

#### Reference: tools/dependency-scan/README.md

<!-- cce:include tools/dependency-scan/README.md -->

#### Reference: tools/dependency-check-maven/README.md

<!-- cce:include tools/dependency-check-maven/README.md -->

#### Reference: tools/sonarqube.md

<!-- cce:include tools/sonarqube.md -->

#### Reference: patterns/governance-side-effect.md

<!-- cce:include patterns/governance-side-effect.md -->

When you have used this procedure, end your reply with the line `procedure: secure-development-and-dependency-scanning`.
