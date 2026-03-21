# typed: false
# frozen_string_literal: true

# Homebrew formula for the El proof-assistant programming language.
# To install locally:
#   brew install --build-from-source ./Formula/el.rb
class El < Formula
  desc "El — proof-assistant programming language by Ahmed Hafdi"
  homepage "https://github.com/polyfdor/matyos_repo"
  version "1.0.9"
  license "MIT"

  # Update this URL to point to the actual release tarball on GitHub
  url "https://github.com/polyfdor/matyos_repo/archive/refs/tags/v1.0.9.tar.gz"
  # sha256 "UPDATE_WITH_ACTUAL_SHA256_OF_TARBALL"

  depends_on "python@3.11"

  def install
    libexec.install Dir["*"]

    (bin/"el").write <<~EOS
      #!/bin/bash
      exec "#{Formula["python@3.11"].opt_bin}/python3" "#{libexec}/el_cli.py" "$@"
    EOS
  end

  test do
    (testpath/"hello.el").write <<~EOS
      ALGORITHM hello {
        show "Hello from El!";
      }
    EOS
    assert_match "Hello from El!", shell_output("#{bin}/el run hello.el")
  end
end
