# Machine-Read Comments and Files to Skip

Some comments are code: a tool reads them, and cutting or rewording one changes what the build, the linter, the type checker or the app does. This file extends the Machine-read kind in `[sdlc-root]/knowledge/coding/comment-discipline.yaml` with tool-specific examples; `sdlc-cleanup-comments` never cuts or edits these. The examples below are common cases, not a complete list. The test is the category: if a compiler, bundler, linter, formatter, type checker, test runner, coverage tool, doc generator, framework or migration runner reads it, it's code.

Before trimming, look at the project's own lint, format and build config for custom directives: a custom ESLint rule that reads a comment tag, a codegen marker, a template engine's comment syntax. Those are machine-read too. A project records its own where the rule's Machine-read kind says.

## Comments a Tool Reads

| Kind | Examples |
|------|----------|
| File headers | `#!/usr/bin/env bash`, `# -*- coding: utf-8 -*-`, `# frozen_string_literal: true`, `// swift-tools-version:5.9`, `# syntax=docker/dockerfile:1`, `# escape=` (Dockerfile parser directives) |
| Lint and type suppressions | `# nosemgrep`, `// eslint-disable-next-line`, `/* eslint-env */`, `/* global */`, `// @ts-ignore`, `// @ts-expect-error`, `// @ts-nocheck`, `// @ts-check`, `# noqa`, `# type: ignore`, `# pyright: ignore`, `# pylint: disable=`, `# mypy:`, `# nosec`, `# shellcheck disable=`, `//nolint`, `// NOLINT`, `# rubocop:disable`, `// swiftlint:disable`, `// biome-ignore`, `#pragma warning disable` |
| Formatter switches | `// prettier-ignore`, `<!-- prettier-ignore -->`, `# fmt: off` / `# fmt: on`, `// clang-format off`, `# isort: skip`, `// swiftformat:disable`, `<!-- markdownlint-disable -->` |
| Coverage | `# pragma: no cover`, `/* istanbul ignore next */`, `/* c8 ignore next */` |
| Comments that make a construct valid or lint-clean | `// falls through` and `/* fallthrough */` (ESLint `no-fallthrough`, GCC `-Wimplicit-fallthrough`), `// SAFETY:` above an `unsafe` block (clippy `undocumented_unsafe_blocks`), a comment that is the only content of a block (`catch (e) { // ignore }` passes ESLint `no-empty`; an empty block fails), a docstring that is a function's whole body (cutting it is a syntax error), a doc comment a linter requires (Rust `missing_docs`, pydocstyle's D1 rules, ESLint `require-jsdoc`) |
| Build and codegen | `//go:build`, `// +build`, `//go:generate`, `//go:embed`, `// #cgo`, `/// <reference path="..." />`, `// Code generated ... DO NOT EDIT.`, `@generated` |
| Bundler and runtime hints | `/* webpackChunkName: "x" */`, `/* @vite-ignore */`, `/*#__PURE__*/`, `/* @__PURE__ */`, `/** @jsx h */`, `// @flow`, `/*! preserved */` (minifiers keep it) |
| Type comments | PEP 484 `# type: List[int]`; JSDoc `@type`, `@param {T}`, `@returns {T}` in JavaScript that is type-checked through JSDoc (`checkJs`, `// @ts-check`) |
| Doc tags tools act on | `@deprecated` (editors strike the symbol through), Go `// Deprecated:`, `@internal` (API extractors drop the symbol), PHP docblock annotations (`@ORM\Column`, `@Route`, `@phpstan-*`, `@psalm-*`) |
| Migration directives | `-- +goose Up`, `-- migrate:up`, `-- +migrate Up`, and any comment in a migration a checksum covers (see Files to Skip) |
| Editor and schema hints | `# yaml-language-server: $schema=...`, `// MARK:` (Xcode's file outline), `#region` / `#endregion` |
| License scanners | `SPDX-License-Identifier:`, `SPDX-FileCopyrightText:` |

## Doc Strings and Doc Comments

A docstring is a string the program can read at run time, not a comment. Doc generators (Sphinx, rustdoc, Javadoc, godoc, C# XML docs) render every doc comment, so being rendered isn't enough to keep one. Keep:

- a docstring whose text a program reads at run time: `--help` built by click, Typer or Fire; OpenAPI descriptions built by FastAPI and similar; doctest and Rust doc-test examples (`///` and `//!` examples run as tests);
- a doc comment that documents a public API beyond its signature (the rule's Public contract kind);
- doc tags a tool acts on (the Doc tags row above, and `@param {T}` in type-checked JavaScript).

A doc-comment line that only repeats the name or the types is cut under the rule's "Repeats the name or the types" kind, like any other comment. When unsure, keep it and list it.

## Files to Skip

Leave these out of scope entirely:

- **Generated files:** a `@generated` or `Code generated ... DO NOT EDIT.` marker, or a path the project's codegen writes. The next generation brings the comments back.
- **Vendored and third-party code:** `vendor/`, `third_party/`, `node_modules/`, copied-in libraries. Not ours to edit.
- **Lockfiles, minified and built output:** `*.lock`, `*.min.js`, `dist/`, `build/`.
- **Applied migrations:** migration tools that store a checksum of each applied file (Flyway, Liquibase and others) fail validation when any byte changes, comments included.
- **Test fixtures and snapshots:** the test compares them byte for byte.
- **Framework-managed files:** `[sdlc-root]/` and `.claude/`. `sdlc-migrate` overwrites them.
- **Prose files:** Markdown, plain text and other docs. Their sentences are content, not comments.
