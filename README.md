<div align="center">

<img src="docs/assets/banner.svg" alt="Creality K1 Print Skill — preparar, visualizar, aprovar e imprimir" width="100%">

# Creality K1 Print Skill

**Seu arquivo. Uma prévia real. Sua aprovação antes de imprimir.**

[![Testes](https://github.com/eep0x10/creality-k1-print-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/eep0x10/creality-k1-print-skill/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](pyproject.toml)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-21655B)](LICENSE)
[![English](https://img.shields.io/badge/docs-English-637D71)](README.en.md)

[Instalar](#comece-aqui) · [Como funciona](#do-modelo-à-k1) · [Documentação](#documentação) · [Downloads](https://github.com/eep0x10/creality-k1-print-skill/releases)

</div>

Uma skill para agentes com acesso ao seu computador prepararem modelos em PLA na **Creality K1 original**: escolher orientação e configurações, reduzir suportes desnecessários, fatiar no OrcaSlicer e mostrar a prévia dos percursos reais. O envio pelo Moonraker só acontece depois do seu aceite daquele arquivo.

## Do modelo à K1

1. **Quem decide?** Primeiro, o agente pergunta se você quer delegar as configurações ou escolhê-las.
2. **Suas prioridades.** No modo manual, escolha robustez ou economia de filamento e velocidade ou beleza/detalhes. No modo delegado, o agente avalia o modelo.
3. **Preparação local.** Geometria, escala uniforme, orientação, suporte, paredes, preenchimento e acabamento.
4. **Prévia real.** PNG do G-code, dimensões, tempo e consumo estimados. A prévia identifica suportes e informa eventual amostragem visual.
5. **Seu aceite.** Somente depois da aprovação o arquivo é enviado e o início é solicitado. Alterar o G-code ou a prévia invalida o aceite anterior.

```mermaid
flowchart LR
  A[Arquivo STL ou 3MF] --> B[GPT decide ou você escolhe]
  B --> C[Preparar e fatiar localmente]
  C --> D[Prévia real e estimativas]
  D --> E{Você aprova?}
  E -- Sim --> F[Upload e início na K1]
  E -- Ajustar --> C
```

## Comece aqui

**Requisitos:** agente com terminal local, Python 3.11+, OrcaSlicer instalado e K1 original com Moonraker 0.10.0 ou superior, API major 1. Root sozinho não instala o Moonraker. O suporte inicial é PLA e bico de 0,4 mm; outras máquinas, materiais e bicos não foram validados.

```powershell
git clone https://github.com/eep0x10/creality-k1-print-skill.git
cd creality-k1-print-skill
python scripts/install_skill.py --with-runtime
```

O instalador copia a skill para `~/.agents/skills/creality-k1-print`, cria um ambiente Python isolado e instala suas dependências. **Não configura nem inicia a impressora e não substitui uma skill já instalada.** Para outro diretório, use `--target`. Consulte o [guia de instalação](skills/creality-k1-print/references/setup.md) para configurar conexão e OrcaSlicer.

Depois, em um agente compatível:

```text
Use $creality-k1-print para configurar minha K1 e preparar este modelo.
Quero que você primeiro pergunte quem vai escolher as configurações.
```

A skill também pode ser instalada pelo instalador de skills do seu agente apontando para a pasta [skills/creality-k1-print](skills/creality-k1-print). Um chat sem executor local não ganha acesso ao computador ou à impressora apenas por receber a skill.

## O que acompanha

| Recurso | Comportamento |
| :--- | :--- |
| Geometria | STL e geometria de 3MF, transformações de montagem e escala uniforme |
| Perfis | Derivados dos recursos oficiais do OrcaSlicer instalado, sem reutilizar G-code externo |
| Prioridades | Robustez/economia e rapidez/detalhe, com modo equilibrado |
| Prévia | Percursos depositados reais, suportes destacados, estimativas e hashes |
| Conexão | Descoberta limitada à rede privada escolhida, consulta de estado e identidade |
| Envio | Arquivo aprovado, verificação de checksum, upload sem início automático e uma solicitação de início |

O núcleo funciona **sem Kiln e sem conta de nuvem**. Kiln é uma integração opcional; [entenda a escolha do transporte nativo](docs/INTEGRATIONS.md).

## Exemplo sintético

Esta imagem usa uma peça original de teste, não um modelo de terceiros. Azul identifica o modelo; laranja identifica os suportes.

![Prévia sintética real dos percursos do OrcaSlicer](docs/assets/toolpath-demo.png)

## Validação e limites

A origem deste fluxo inclui um início de impressão confirmado em uma K1 com Moonraker. Isso não comprova a conclusão ou a qualidade física de qualquer peça. O pacote público é testado com geometria sintética e requisições simuladas; não usa a impressora real como parte dos testes.

Os perfis são pontos de partida. A calibração física do seu rolo, a limpeza da mesa, o carregamento de PLA e a remoção dos suportes continuam necessários. Não há garantia de orientação ótima ou sucesso físico. Não há túnel pela internet, servidor público ou serviço permanente de monitoramento instalado. Veja [limites de operação](skills/creality-k1-print/references/operating-limits.md).

## Documentação

| Guia | Conteúdo |
| :--- | :--- |
| [Instalação](skills/creality-k1-print/references/setup.md) | Ambiente isolado, conexão, recursos Orca e comandos |
| [Fluxo de impressão](skills/creality-k1-print/references/workflow.md) | Preferências, preparação, prévia e aceite vinculado ao arquivo |
| [Arquitetura](docs/ARCHITECTURE.md) | Componentes, manifesto e transmissão |
| [Integrações](docs/INTEGRATIONS.md) | Moonraker, OrcaSlicer, fontes de modelos e Kiln opcional |
| [Privacidade](docs/PRIVACY.md) | Arquivos locais, segredos, rede e publicação |
| [Testes](docs/TESTING.md) | Comandos reproduzíveis, evidências e limites da validação |
| [Contribuir](CONTRIBUTING.md) | Desenvolvimento e revisão |

Projeto independente, sem afiliação ou endosso da Creality. Código próprio sob [MIT](LICENSE); ferramentas externas mantêm suas próprias [licenças e avisos](THIRD_PARTY_NOTICES.md).
