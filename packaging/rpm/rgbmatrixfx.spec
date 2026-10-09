# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Built by packaging/build-rpm.sh (and .github/workflows/release.yml), which sets
# rfx_version (RPM form, e.g. 1.1.0 or 1.1.0~rc.1) and rfx_upstream (1.1.0 / 1.1.0-rc.1),
# and fills in the @CHANGELOG@ entry.
%{!?rfx_upstream: %global rfx_upstream 0}
%{!?rfx_version: %global rfx_version %{rfx_upstream}}
# fallbacks for building outside Fedora/openSUSE (their macro packages define these)
%{!?_userunitdir: %global _userunitdir %{_prefix}/lib/systemd/user}
%{!?python3: %global python3 /usr/bin/python3}

Name:           rgbmatrixfx
Version:        %{rfx_version}
Release:        1%{?dist}
Summary:        Chroma-style lighting effects for RGB keyboards and mice
License:        GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
URL:            https://github.com/nitrofireinc-pixel/RGBMatrixFX
Source0:        %{url}/archive/refs/tags/v%{rfx_upstream}.tar.gz#/rgbmatrixfx-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  systemd-rpm-macros
Requires:       python3
Requires:       python3-pyside6
Requires:       python3-numpy
Requires:       python3-dbus
# python3-openrazer and openrazer-daemon come from the OpenRazer repository
# (https://openrazer.github.io/#fedora, OBS hardware:razer)
Requires:       python3-openrazer
Recommends:     openrazer-daemon
# OpenRGB lists motherboard / RAM / fan lighting (its package brings the udev rules)
Recommends:     openrgb
Obsoletes:      razorfx < 1.2.1
Provides:       razorfx = %{version}-%{release}
Recommends:     python3-evdev
Suggests:       pipewire-utils

%description
RGBMatrixFX (formerly RazorFX) renders animated lighting effects onto Razer keyboards and mice
through the OpenRazer driver and daemon, and reacts to key presses, mouse
clicks and scrolling. A small background engine (a systemd user service)
keeps the lighting running; the window lets you pick and tune effects live,
build presets and manage per-zone lighting. It follows the desktop's light or
dark theme.

Not affiliated with or endorsed by Razer Inc.
Razer is a trademark of Razer Inc.

%prep
%autosetup -n RGBMatrixFX-%{rfx_upstream}

%build
# pure Python, nothing to build

%install
DESTDIR=%{buildroot} PREFIX=%{_prefix} PYTHON=%{python3} UNITDIR=%{_userunitdir} \
    DOCDIR=%{_docdir}/%{name} sh packaging/install-tree.sh
%{?py_byte_compile:%py_byte_compile %{python3} %{buildroot}%{_datadir}/rgbmatrixfx}

%check
%{python3} -c "import sys; sys.path.insert(0, '%{buildroot}%{_datadir}/rgbmatrixfx'); import rgbmatrixfx, rgbmatrixfx.layout, rgbmatrixfx.plugin_api; print(rgbmatrixfx.__version__)"

# The user unit is installed but not enabled (no preset): "Start engine at login" is each
# user's choice, and the RGBMatrixFX window enables it for the user on first start.

%files
%license LICENSE LICENSE-EXCEPTION
%{_docdir}/%{name}/
%{_bindir}/rgbmatrixfx
%{_bindir}/rgbmatrixfx-engine
%{_datadir}/rgbmatrixfx/
%{_datadir}/applications/rgbmatrixfx.desktop
%{_datadir}/icons/hicolor/*/apps/rgbmatrixfx.*
%{_datadir}/metainfo/io.github.nitrofireinc_pixel.rgbmatrixfx.metainfo.xml
%{_mandir}/man1/rgbmatrixfx.1*
%{_mandir}/man1/rgbmatrixfx-engine.1*
%{_userunitdir}/rgbmatrixfx-engine.service
%{_userunitdir}/openrgb-server.service
%{_prefix}/lib/modules-load.d/rgbmatrixfx-i2c.conf

%changelog
@CHANGELOG@
