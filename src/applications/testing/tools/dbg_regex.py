import re

raw_str = """Given I start my Streamline application
                Navigating to URL: https://webappisamdev.asbbank.co.nz/public/join/asb/?grcDisabled=true
                -&gt; done: CommonSteps.GivenIStartMyStreamlineApplication() (0.7s)
                Given I am in the Clever Kash Introduction page
                Navigating to URL: https://webappisamdev.asbbank.co.nz/public/join/cleverkash/?grcDisabled=true
                -&gt; done: CommonSteps.GivenIAmInTheCleverKashIntroductionPage() (0.4s)
                And I am in the Introduction page
                12/6/2017 2:04:50 AMWaitForFeaturesPageLoad: Executing WaitForFrameAndSwitch
                12/6/2017 2:04:51 AMWaitForFeaturesPageLoad: Done executing WaitForFrameAndSwitch
                -&gt; done: IntroductionPageSteps.GivenIAmInTheIntroductionPage() (20.2s)
                Then the header image is displayed
                -&gt; done: IntroductionPageSteps.ThenTheHeaderImageIsDisplayed() (0.1s)
                And the Introduction heading and info text is displayed
                -&gt; done: IntroductionPageSteps.ThenTheIntroductionHeadingAndInfoTextIsDisplayed() (0.1s)
                And the It's easy to join section for Clever Kash is not displayed
                -&gt; done: IntroductionPageSteps.ThenTheItSEasyToJoinSectionForCleverKashIsNotDisplayed() (10.2s)
                And the Before you start section is displayed
                -&gt; done: IntroductionPageSteps.ThenTheBeforeYouStartSectionIsDisplayed() (0.2s)
                And the 'Over 18' tri-state controls has no default selection
                -&gt; done: IntroductionPageSteps.ThenTheTriStateControlsHasNoDefaultSelection("Over 18") (0.1s)
                And the 'NZ Resident' tri-state controls has no default selection
                -&gt; done: IntroductionPageSteps.ThenTheTriStateControlsHasNoDefaultSelection("NZ Resident") (0.1s)
                And the footer elements are displayed
                -&gt; done: IntroductionPageSteps.ThenTheFooterElementsAreDisplayed() (0.3s)
            """


regex = re.compile("(.*)\s+")
find_result = re.findall(regex, raw_str)

steps = list()
dict_data = dict()
tmp = list()

for item in find_result:
    result = re.match('-&gt;\s(?P<status>\w+):\s(?P<step_name>.*)\s\S(?P<execution_time>\d+\.\d+\w+)', item)

    if result:
        dict_data.update(dict(
            step_name=result.groups()[1],
            step_status=result.groups()[0],
            step_execution_time=result.groups()[2],
            step_log='\n'.join(tmp)
        ))
        steps.append(dict_data)

        dict_data = dict()
        tmp = list()
        continue

    else:
        tmp.append(item)


for i in raw_str.splitlines():
    print('=\t', i)

for x in steps:
    print('#\t', x)