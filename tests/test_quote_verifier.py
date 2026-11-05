"""verify_quote: tolerant of extraction noise and elisions, still strict about edited or invented quotes. Offline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage3_summarizer.quote_verifier import verify_quote  # noqa: E402

CHUNK = ("the Switch Transformer [4] routes each token to a single expert ( K = 1 ) for maximal efficiency, while GShard, Mixtral, and "
         "OLMoE use topK routing with K &lt; N experts [28, 5, 6]. To counteract this, MoE models add a differentiable auxiliary "
         "load-balancing loss [28, 4]. The router computes expert selection logits and the top-k experts are selected after a softmax.")


def test_exact_and_case_and_spacing():
    assert verify_quote("The router computes expert selection logits and the top-k experts are selected", [CHUNK])
    assert verify_quote("the  ROUTER computes expert selection logits and the top-k experts are selected", [CHUNK])


def test_citation_markers_and_parenthesis_spaces_do_not_matter():
    assert verify_quote("the Switch Transformer routes each token to a single expert (K = 1) for maximal efficiency", [CHUNK])
    assert verify_quote("To counteract this, MoE models add a differentiable auxiliary load-balancing loss [28, 4].", [CHUNK])


def test_html_entities_and_typographic_hyphens():
    assert verify_quote("OLMoE use topK routing with K < N experts", [CHUNK])
    assert verify_quote("MoE models add a differentiable auxiliary load\u2011balancing loss", [CHUNK])


def test_an_elision_is_accepted_when_every_piece_is_real():
    assert verify_quote("The router computes expert selection logits ... the top-k experts are selected after a softmax", [CHUNK])
    assert verify_quote("the Switch Transformer routes each token to a single expert [...] To counteract this, MoE models add", [CHUNK])


def test_an_elision_with_an_invented_piece_fails():
    assert not verify_quote("The router computes expert selection logits ... and then the experts vote by majority", [CHUNK])


def test_two_sentences_joined_without_an_elision_still_fail():
    """The edited quotes found in the Q2 run: the digest model joined clauses and dropped words, so there is no contiguous passage."""
    assert not verify_quote("Switch Transformer routes each token to a single expert (K = 1), while GShard, Mixtral, and OLMoE use topK "
                            "routing, and the loss is minimized when both quantities are uniform", [CHUNK])


def test_paraphrase_and_short_quotes_fail():
    assert not verify_quote("Each token is sent to exactly one expert in the Switch Transformer design", [CHUNK])
    assert not verify_quote("the router", [CHUNK])
    assert not verify_quote("", [CHUNK])
    assert not verify_quote("... ...", [CHUNK])
