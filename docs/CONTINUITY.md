# Continuar em outro PC ou com outra IA

O GitHub contém código, skill, testes, instruções e conhecimento reutilizável. **Trabalhos reais e configuração da impressora são privados.** Para manter o histórico do proprietário, transfira também seu pacote privado local. Um clone público sozinho não contém fotos, modelos baixados, G-code, perfis derivados, recibos ou credenciais.

## 1. Obter e conferir o projeto público

Requisitos: Git, Python 3.11+ e acesso a um terminal local. O ambiente Python não deve ser copiado de outro PC.

```powershell
git clone https://github.com/eep0x10/creality-k1-print-skill.git
cd creality-k1-print-skill
git status --short
git log -1 --oneline
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe scripts/audit_publication.py
.venv/Scripts/python.exe -m k1print --help
.venv/Scripts/python.exe -m k1print snapshot --help
```

No Linux/macOS, use `python3 -m venv .venv` e substitua `.venv/Scripts/python.exe` por `.venv/bin/python`. A CI cobre Windows/Linux; macOS ainda exige validação local do executável e dos recursos Orca. Esses comandos de teste/ajuda não precisam da impressora e não iniciam impressão.

Você também pode usar o ZIP de uma [release](https://github.com/eep0x10/creality-k1-print-skill/releases). Confira `SHA256SUMS` e mantenha a pasta inteira, incluindo documentação. Um ZIP de release é uma cópia do código; um clone Git preserva também o histórico de commits e facilita continuar o desenvolvimento.

Em um ZIP extraído da versão 0.3.0+, execute `python scripts/verify_release.py .` **antes** de criar ambientes/arquivos nessa pasta. O verificador confere o manifesto do commit sem precisar de Git. A auditoria de publicação (`audit_publication.py`) é destinada ao checkout Git; não deve ser apresentada como teste de um ZIP sem `.git`. Os hashes verificam integridade e vínculo ao commit declarado; obtenha o ZIP/checksum pela release autorizada para confirmar a origem.

## 2. Instalar a skill no novo host

```sh
python scripts/install_skill.py --with-runtime
```

O padrão é `~/.agents/skills/creality-k1-print`. Outros hosts podem usar outra pasta: consulte sua documentação e passe `--target`. A descoberta automática depende do cliente; ter o arquivo no disco não prova que a IA o carregou.

O instalador preserva destinos existentes. Para atualizar uma instalação antiga, faça antes um backup privado fora das pastas de descoberta de skills, registre suas personalizações e instale em um destino novo/vazio. Compare e reaplique somente suas alterações verificadas; não copie `.venv`. Se a cópia já existe mas a instalação das dependências falhou, use `--repair-runtime` para reconstruir apenas o ambiente da skill reconhecida. Esse reparo não atualiza nem substitui suas instruções ou scripts locais.

## 3. Configurar impressora e Orca neste PC

Instale o OrcaSlicer oficial. 2.4.2 foi a versão de CLI exercida no fluxo original; outro executável/versão pode alterar herança, flags, estimativas e percursos. Registre a versão usada e mantenha perfis originais intactos.

Configure endereço/hostname corretos da sua própria impressora e os caminhos deste PC. [config.example.json](../config.example.json) ilustra o esquema com placeholders; não é uma configuração pronta. Uma rota de recursos explícita pode ser necessária para macOS ou distribuições AppImage/Linux.

```sh
k1print init --printer-url http://k1.local:7125 --expected-hostname YOUR_K1_HOSTNAME --orca-path /path/to/orca-slicer --orca-resources /path/to/resources
```

Os comandos curtos pressupõem o ambiente ativado ou no PATH. No Windows, use `.venv/Scripts/k1print.exe`; no Linux, `.venv/bin/k1print`. `init` é local e não contacta a impressora. Quando a conexão for de fato necessária/autorizada, consulte `status` e confira a identidade. API keys são fornecidas por variável de ambiente local, nunca pelo GitHub. Não copie arquivos de autenticação, cookies ou sessões para o pacote público.

Mover o projeto para outro PC não cria acesso pela internet à K1. O PC deve alcançar a impressora pela rede autorizada. Nenhum túnel, porta pública ou serviço permanente é instalado.

## 4. Restaurar trabalhos privados

Guarde o pacote privado em armazenamento confiável, fora deste checkout. Ele pode conter fotos pessoais, endereços da rede, caminhos antigos e trabalhos sujeitos à licença do modelo. Não envie o arquivo inteiro a outra pessoa ou serviço sem revisar o conteúdo.

1. Confira o checksum do ZIP e o manifesto por arquivo fornecidos com o pacote. Extraia em uma pasta nova e preserve os arquivos originais.
2. Mantenha cada trabalho completo: fonte/proveniência, perfis, geometria, G-code, PNG, relatório, manifesto e **recibo**. `job.json` sozinho não preserva o trabalho.
3. Confira hashes antes de usar os artefatos. Caminhos relativos de `job.json` permitem validar uma pasta movida; scripts legados podem ter caminhos absolutos e devem ser revisados antes de executar. Nunca regrave automaticamente referências dentro de G-code/relatórios aprovados.
4. Recrie `.venv` e reinstale ferramentas oficiais. Configure a conexão para o novo PC e forneça credenciais separadamente. A migração não instala firmware nem muda a impressora.
5. Um recibo e uma aprovação antiga são histórico. **Não inicie novamente um trabalho restaurado.** Para uma repetição intencional, crie um novo trabalho, mostre a prévia e obtenha um novo aceite. Não apague recibos para contornar isso.

## 5. Reutilizar ajustes próprios ao fatiar novamente

`prepare` sem opções de perfil deriva valores genéricos do Orca. Para manter ajustes próprios, forneça um diretório privado com **machine.json**, **process.json** e **filament.json**, completos e sem herança `inherits`.

```sh
k1print prepare /private/models/model.stl --job-dir /private/jobs/new-job --profiles-dir /private/profiles/my-k1-pla
```

Não combine `--profiles-dir` com `--strength`/`--finish`: os perfis completos são a escolha explícita dos ajustes. O importador verifica o escopo K1/PLA/bico 0,4, recusa processamento externo e copia os perfis para um novo trabalho, preservando originais e hashes. Isso não comprova calibração física; mantenha os resultados medidos e a condição de candidato/calibrado no registro privado. Verifique os valores realmente exportados no G-code.

Um perfil adaptado de acabamento com várias alterações não isola uma causa de defeito. Use [a revisão física](../skills/creality-k1-print/references/physical-quality.md) para aprender com os resultados.

## 6. Mensagem para a próxima IA

```text
Continue o projeto deste checkout. Leia primeiro AGENTS.md,
docs/AI_GUIDE.md, docs/PROJECT_STATE.md e docs/CONTINUITY.md.
Inspecione branch, status, histórico e arquivos atuais; preserve alterações existentes.
Execute os testes offline antes de afirmar que funciona neste PC.
Considere apenas evidência comprovada e mantenha limitações explícitas.
Configuração, fotos, modelos e trabalhos reais ficam no pacote privado fornecido separadamente.
Não opere a impressora durante desenvolvimento ou instalação.
Para uma nova impressão, siga a escolha inicial de decisões, prévia real e aprovação final.
Retome pelo próximo passo registrado, sem reenviar trabalhos antigos.
```

O projeto não depende de acesso ao chat original ou a uma memória de IA proprietária. Novas decisões relevantes devem ser registradas nos arquivos de projeto apropriados, mantendo segredos e estado operacional privado fora do GitHub.
