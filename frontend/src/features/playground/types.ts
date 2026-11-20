export type PlaygroundSource =
    | { kind: "file"; file: File }
    | { kind: "url"; url: string };
